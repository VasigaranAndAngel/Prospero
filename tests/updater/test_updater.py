"""Tests for the updater state machine and update archive extraction.

Downloads go through the fixture HTTP server. Installation is exercised separately by calling
the worker directly, so no test depends on a real launcher or on QApplication quitting.
"""

import io
import json
import sys
import tarfile
import zipfile
from collections.abc import Callable, Iterator
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from arg_parser import args
from constants import APPLICATION_VERSION
from helpers.singleton_meta import SingletonMeta
from network import Downloaded, NetworkClient, NetworkError
from platform_specific import IS_WINDOWS
from platform_specific.paths import app_executable, version_dir
from platform_specific.updater import APP_EXECUTABLE_NAME
from updater import GithubLatestRelease, UpdateInfo, Updater, UpdateStatus

Pump = Callable[[Callable[[], bool]], bool]

ORIGINAL_INSTALL = Updater.install
"The autouse fixture stubs this; the end-to-end test restores it."

BAD_PAYLOAD: bytes = b'{"unexpected": true}'
"Valid JSON that does not match the GithubLatestRelease model."


def archive_suffix() -> str:
    return "windows-x86_64.zip" if IS_WINDOWS else "linux-x86_64.tar.gz"


def archive_name(tag: str = "99.0.0") -> str:
    return f"Prospero-{tag}-{archive_suffix()}"


def make_archive(files: dict[str, bytes]) -> bytes:
    """Build a small update archive in the same shape the release workflow publishes."""
    buffer = io.BytesIO()
    if IS_WINDOWS:
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, data in files.items():
                archive.writestr(name, data)
    else:
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            for name, data in files.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = 0o755
                archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def release_payload(
    tag: str,
    asset_url: str,
    asset_size: int,
    *,
    asset_name: str | None = None,
    digest: str | None = None,
) -> bytes:
    """Build a GitHub release payload shaped like the real API response."""
    return json.dumps(
        {
            "tag_name": tag,
            "name": f"Prospero {tag}",
            "body": "notes",
            "assets": [
                {
                    "browser_download_url": asset_url,
                    "name": asset_name or archive_name(tag),
                    "label": None,
                    "state": "uploaded",
                    "content_type": "application/octet-stream",
                    "size": asset_size,
                    "digest": digest,
                }
            ],
        }
    ).encode()


def release_from(base_url: str, payload: bytes) -> GithubLatestRelease:
    NetworkClient.set_base_url("github", base_url)
    return GithubLatestRelease.model_validate_json(payload)


@pytest.fixture(autouse=True)
def default_server_state(http_server: Any) -> None:  # pyright: ignore[reportAny, reportExplicitAny]
    """Keep one test's server payload from deciding the next test's result."""
    http_server.release_payload = BAD_PAYLOAD
    http_server.update_bytes = b""


@pytest.fixture(autouse=True)
def block_auto_install(monkeypatch: pytest.MonkeyPatch) -> None:
    """Download tests must not race the automatic installer timer."""
    monkeypatch.setattr(Updater, "install", lambda self, path: True)


@pytest.fixture
def updater(
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[Updater]:
    """A fresh Updater with an isolated install root and the fixture's NetworkClient."""
    monkeypatch.setattr(args, "update_domain", None)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr("updater._can_self_update", lambda: True)
    monkeypatch.setenv("PROSPERO_INSTALL_ROOT", str(tmp_path / "install"))
    monkeypatch.delitem(SingletonMeta._instances, Updater, raising=False)  # pyright: ignore[reportPrivateUsage]
    instance = Updater()
    yield instance
    instance.cancel_update()
    monkeypatch.delitem(SingletonMeta._instances, Updater, raising=False)  # pyright: ignore[reportPrivateUsage]


# region public surface


def test_github_fetch_error_is_the_shared_network_error() -> None:
    assert Updater.GithubFetchError is NetworkError
    assert isinstance(NetworkError("boom"), Updater.GithubFetchError)


def test_downloaded_is_the_shared_progress_type() -> None:
    from updater import Downloaded as UpdaterDownloaded

    assert UpdaterDownloaded is Downloaded


def test_result_widget_imports_still_resolve() -> None:
    from providers.command_provider._updater_result_widget import UpdaterResultWidget

    assert UpdaterResultWidget is not None


# endregion


# region domain override


def test_update_domain_registers_base_url(
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(args, "update_domain", ["https://mirror.test"])
    monkeypatch.delitem(SingletonMeta._instances, Updater, raising=False)  # pyright: ignore[reportPrivateUsage]
    _ = Updater()

    assert NetworkClient.resolve("github", "https://api.github.com") == "https://mirror.test"


def test_default_domain_used_without_override(offline: NetworkClient, updater: Updater) -> None:  # pyright: ignore[reportUnusedParameter]
    assert NetworkClient.resolve("github", "https://api.github.com") == "https://api.github.com"


# endregion


# region offline


def test_offline_get_latest_release_reports_error(offline: NetworkClient, updater: Updater) -> None:  # pyright: ignore[reportUnusedParameter]
    results: list[GithubLatestRelease | NetworkError] = []

    updater.get_latest_release(results.append)

    assert len(results) == 1
    assert isinstance(results[0], NetworkError)


def test_offline_check_update_emits_error(offline: NetworkClient, updater: Updater) -> None:  # pyright: ignore[reportUnusedParameter]
    emitted: list[UpdateInfo] = []
    _ = updater.update_info_updated.connect(emitted.append)

    updater.check_update()

    assert len(emitted) == 2, "checking and the error result should both be emitted"
    assert emitted[-1].state is UpdateStatus.none
    assert isinstance(emitted[-1].error, NetworkError)
    assert emitted[-1].update_available is None


# endregion


# region fetching releases


def test_get_latest_release_parses_payload(
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    base_url: str,
    http_server: Any,  # pyright: ignore[reportAny, reportExplicitAny]
    updater: Updater,
    pump_until: Pump,
) -> None:
    http_server.release_payload = release_payload("99.0.0", f"{base_url}/file/10", 10)
    NetworkClient.set_base_url("github", base_url)
    results: list[GithubLatestRelease | NetworkError] = []

    updater.get_latest_release(results.append)

    assert pump_until(lambda: len(results) == 1), "release was never fetched"
    assert isinstance(results[0], GithubLatestRelease)
    assert results[0].tag_name == "99.0.0"
    assert str(results[0].get_version()) == "99.0.0"


def test_get_latest_release_reports_bad_payload(
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    base_url: str,
    updater: Updater,
    pump_until: Pump,
) -> None:
    NetworkClient.set_base_url("github", base_url)
    results: list[GithubLatestRelease | NetworkError] = []

    updater.get_latest_release(results.append)

    assert pump_until(lambda: len(results) == 1)
    assert isinstance(results[0], NetworkError)
    assert "Unexpected release payload" in results[0].error_str


def test_check_update_reports_newer_release(
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    base_url: str,
    http_server: Any,  # pyright: ignore[reportAny, reportExplicitAny]
    updater: Updater,
    pump_until: Pump,
) -> None:
    http_server.release_payload = release_payload("999.0.0", f"{base_url}/file/10", 10)
    NetworkClient.set_base_url("github", base_url)
    emitted: list[UpdateInfo] = []
    _ = updater.update_info_updated.connect(emitted.append)

    updater.check_update()

    assert pump_until(lambda: emitted and emitted[-1].state is UpdateStatus.update_checked)
    info = emitted[-1]
    assert info.update_available is True
    assert info.latest_release is not None
    assert info.latest_release.tag_name == "999.0.0"
    assert info.error is None


def test_check_update_reports_up_to_date(
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    base_url: str,
    http_server: Any,  # pyright: ignore[reportAny, reportExplicitAny]
    updater: Updater,
    pump_until: Pump,
) -> None:
    http_server.release_payload = release_payload(
        str(APPLICATION_VERSION), f"{base_url}/file/10", 10
    )
    NetworkClient.set_base_url("github", base_url)
    emitted: list[UpdateInfo] = []
    _ = updater.update_info_updated.connect(emitted.append)

    updater.check_update()

    assert pump_until(lambda: emitted and emitted[-1].state is UpdateStatus.update_checked)
    assert emitted[-1].update_available is False
    assert emitted[-1].latest_release is None


# endregion


# region downloading


def test_download_verifies_and_completes(
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    base_url: str,
    http_server: Any,  # pyright: ignore[reportAny, reportExplicitAny]
    updater: Updater,
    pump_until: Pump,
) -> None:
    archive = make_archive({"Prospero/Prospero": b"binary"})
    digest = "sha256:" + sha256(archive).hexdigest()
    http_server.update_bytes = archive
    release = release_from(
        base_url,
        release_payload("99.0.0", f"{base_url}/update.tar.gz", len(archive), digest=digest),
    )

    assert updater.download(release) is True
    assert pump_until(
        lambda: updater.update_info.state is UpdateStatus.downloaded
    ), "archive never downloaded"
    final = updater.update_info.download_progress
    assert final is not None
    assert final.completed is True
    assert final.downloaded_size == len(archive)
    assert final.file_path.exists()
    assert final.file_path.stat().st_size == len(archive)
    assert not list(final.file_path.parent.glob("*.part"))


def test_second_download_is_ignored_while_one_runs(
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    base_url: str,
    file_size: int,
    updater: Updater,
    pump_until: Pump,
) -> None:
    release = release_from(
        base_url,
        release_payload("99.0.0", f"{base_url}/slow/{file_size}", file_size),
    )

    assert updater.download(release) is True
    assert updater.download(release) is False
    assert pump_until(
        lambda: (dp := updater.update_info.download_progress) is not None
        and dp.downloaded_size > 0
    )
    updater.cancel_update()


def test_cancel_update_when_idle_does_nothing(updater: Updater) -> None:
    emitted: list[UpdateInfo] = []
    _ = updater.update_info_updated.connect(emitted.append)

    updater.cancel_update()

    assert emitted == []


def test_cancel_update_stops_in_flight_download(
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    base_url: str,
    file_size: int,
    updater: Updater,
    pump_until: Pump,
) -> None:
    release = release_from(
        base_url,
        release_payload("99.0.0", f"{base_url}/slow/{file_size}", file_size),
    )

    assert updater.download(release) is True
    assert pump_until(
        lambda: (dp := updater.update_info.download_progress) is not None
        and dp.downloaded_size > 0
    ), "nothing arrived"
    updater.cancel_update()

    assert pump_until(
        lambda: updater.update_info.state is UpdateStatus.download_aborted
    ), "cancel was never reported"
    assert updater.update_info.download_progress is not None
    assert updater.update_info.download_progress.aborted is True
    assert updater.update_info.download_progress.completed is False
    assert updater.update_info.error is None


def test_download_can_be_retried_after_cancel(
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    base_url: str,
    file_size: int,
    updater: Updater,
    pump_until: Pump,
) -> None:
    release = release_from(
        base_url,
        release_payload("99.0.0", f"{base_url}/slow/{file_size}", file_size),
    )

    assert updater.download(release) is True
    assert pump_until(
        lambda: (dp := updater.update_info.download_progress) is not None
        and dp.downloaded_size > 0
    )
    updater.cancel_update()
    assert pump_until(
        lambda: updater.update_info.state is UpdateStatus.download_aborted
    )

    assert updater.download(release) is True
    assert pump_until(
        lambda: updater.update_info.state is UpdateStatus.downloading
        and (dp := updater.update_info.download_progress) is not None
        and dp.downloaded_size > 0
    ), "retry never started transferring"
    updater.cancel_update()


def test_size_mismatch_does_not_install(
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    base_url: str,
    http_server: Any,  # pyright: ignore[reportAny, reportExplicitAny]
    updater: Updater,
    pump_until: Pump,
) -> None:
    archive = make_archive({"Prospero/Prospero": b"binary"})
    http_server.update_bytes = archive
    release = release_from(
        base_url,
        release_payload("99.0.0", f"{base_url}/update.tar.gz", len(archive) + 1),
    )

    assert updater.download(release) is True
    assert pump_until(
        lambda: updater.update_info.state is UpdateStatus.update_checked
        and updater.update_info.error is not None
    )
    assert "size mismatch" in str(updater.update_info.error)


def test_digest_mismatch_does_not_install(
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    base_url: str,
    http_server: Any,  # pyright: ignore[reportAny, reportExplicitAny]
    updater: Updater,
    pump_until: Pump,
) -> None:
    archive = make_archive({"Prospero/Prospero": b"binary"})
    http_server.update_bytes = archive
    release = release_from(
        base_url,
        release_payload(
            "99.0.0",
            f"{base_url}/update.tar.gz",
            len(archive),
            digest="sha256:" + "0" * 64,
        ),
    )

    assert updater.download(release) is True
    assert pump_until(
        lambda: updater.update_info.state is UpdateStatus.update_checked
        and updater.update_info.error is not None
    )
    assert "digest mismatch" in str(updater.update_info.error)


# endregion


# region installing


def test_download_refuses_outside_an_installed_build(
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    base_url: str,
    updater: Updater,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("updater._can_self_update", lambda: False)
    release = release_from(
        base_url,
        release_payload("99.0.0", f"{base_url}/update.tar.gz", 10),
    )

    assert updater.download(release) is False
    assert updater.update_info.state is UpdateStatus.update_checked
    assert "installed build" in str(updater.update_info.error)


def test_download_auto_installs_and_activates(
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    base_url: str,
    http_server: Any,  # pyright: ignore[reportAny, reportExplicitAny]
    updater: Updater,
    monkeypatch: pytest.MonkeyPatch,
    pump_until: Pump,
) -> None:
    archive = make_archive({
        "Prospero/Prospero": b"binary",
        "Prospero/_internal/data.txt": b"payload",
    })
    digest = "sha256:" + sha256(archive).hexdigest()
    http_server.update_bytes = archive
    release = release_from(
        base_url,
        release_payload("99.0.0", f"{base_url}/update.tar.gz", len(archive), digest=digest),
    )

    committed: list[str] = []
    restarted: list[int] = []
    monkeypatch.setattr(Updater, "install", ORIGINAL_INSTALL)
    monkeypatch.setattr("updater.commit_install", lambda value: committed.append(value) or True)
    monkeypatch.setattr("updater.restart_app", lambda: restarted.append(1) or True)

    assert updater.download(release) is True
    assert pump_until(lambda: bool(committed)), "download was never installed and activated"
    assert committed == [release.directory_version()]
    assert pump_until(lambda: bool(restarted)), "installer never requested a restart"
    assert updater.update_info.state is UpdateStatus.restart_queue
    assert (version_dir(release.directory_version()) / "Prospero" / APP_EXECUTABLE_NAME).is_file()


def test_install_extracts_a_versioned_directory(
    updater: Updater,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    pump_until: Pump,
) -> None:
    archive = make_archive(
        {
            "Prospero/Prospero": b"binary",
            "Prospero/_internal/data.txt": b"payload",
            "install.sh": b"ignored",
        }
    )
    archive_path = tmp_path / archive_name()
    archive_path.write_bytes(archive)

    release = GithubLatestRelease.model_validate_json(
        release_payload("99.0.0", "https://example.com/update", len(archive))
    )
    version = release.directory_version()
    updater.update_info.state = UpdateStatus.downloaded
    updater.update_info.latest_release = release
    updater._install_version = version  # pyright: ignore[reportPrivateUsage]

    committed: list[str] = []
    restarted: list[int] = []

    def commit(value: str) -> bool:
        committed.append(value)
        return True

    monkeypatch.setattr("updater.commit_install", commit)
    monkeypatch.setattr("updater.restart_app", lambda: restarted.append(1) or True)

    updater._install_worker(version, archive_path)  # pyright: ignore[reportPrivateUsage]

    assert pump_until(lambda: bool(committed)), "installer never committed the version"
    assert committed == [version]
    assert pump_until(lambda: bool(restarted)), "installer never requested a restart"
    assert (version_dir(version) / "Prospero" / APP_EXECUTABLE_NAME).is_file()
    assert (version_dir(version) / "Prospero" / "_internal" / "data.txt").is_file()
    assert not (version_dir(version) / "install.sh").exists()
    assert app_executable(version).exists()
    assert updater.update_info.state is UpdateStatus.restart_queue


@pytest.mark.skipif(IS_WINDOWS, reason="Linux tar archives preserve PyInstaller symlinks")
def test_install_preserves_safe_relative_symlinks(
    updater: Updater,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    pump_until: Pump,
) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive_file:
        executable = tarfile.TarInfo("Prospero/Prospero")
        executable.size = 6
        executable.mode = 0o755
        archive_file.addfile(executable, io.BytesIO(b"binary"))

        # Real PyInstaller output uses links such as this into PySide6/Qt/lib.
        link = tarfile.TarInfo("Prospero/_internal/libQt6Core.so.6")
        link.type = tarfile.SYMTYPE
        link.linkname = "PySide6/Qt/lib/libQt6Core.so.6"
        archive_file.addfile(link)

        target = tarfile.TarInfo("Prospero/_internal/PySide6/Qt/lib/libQt6Core.so.6")
        target.size = 7
        target.mode = 0o755
        archive_file.addfile(target, io.BytesIO(b"payload"))

    archive = buffer.getvalue()
    archive_path = tmp_path / archive_name()
    archive_path.write_bytes(archive)
    release = GithubLatestRelease.model_validate_json(
        release_payload("99.0.0", "https://example.com/update", len(archive))
    )
    version = release.directory_version()
    updater.update_info.state = UpdateStatus.downloaded
    updater.update_info.latest_release = release
    updater._install_version = version  # pyright: ignore[reportPrivateUsage]
    committed: list[str] = []
    monkeypatch.setattr("updater.commit_install", lambda value: committed.append(value) or True)
    monkeypatch.setattr("updater.restart_app", lambda: True)

    updater._install_worker(version, archive_path)  # pyright: ignore[reportPrivateUsage]

    assert pump_until(lambda: bool(committed)), "installer never committed the version"
    extracted = version_dir(version) / "Prospero" / "_internal" / "libQt6Core.so.6"
    assert extracted.is_symlink()
    assert extracted.read_bytes() == b"payload"


@pytest.mark.skipif(IS_WINDOWS, reason="Linux tar archives preserve PyInstaller symlinks")
def test_install_rejects_escaping_symlinks(
    updater: Updater,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    pump_until: Pump,
) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive_file:
        executable = tarfile.TarInfo("Prospero/Prospero")
        executable.size = 6
        executable.mode = 0o755
        archive_file.addfile(executable, io.BytesIO(b"binary"))

        link = tarfile.TarInfo("Prospero/evil")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside"
        archive_file.addfile(link)

    archive = buffer.getvalue()
    archive_path = tmp_path / archive_name()
    archive_path.write_bytes(archive)
    release = GithubLatestRelease.model_validate_json(
        release_payload("99.0.0", "https://example.com/update", len(archive))
    )
    version = release.directory_version()
    updater.update_info.state = UpdateStatus.downloaded
    updater.update_info.latest_release = release
    updater._install_version = version  # pyright: ignore[reportPrivateUsage]
    committed: list[str] = []
    monkeypatch.setattr("updater.commit_install", lambda value: committed.append(value) or True)
    monkeypatch.setattr("updater.restart_app", lambda: True)

    updater._install_worker(version, archive_path)  # pyright: ignore[reportPrivateUsage]

    assert pump_until(lambda: updater.update_info.error is not None)
    assert committed == []
    assert not (version_dir(version) / "outside").exists()


def test_install_rejects_path_traversal(
    updater: Updater,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    pump_until: Pump,
) -> None:
    if IS_WINDOWS:
        archive = make_archive({"Prospero/Prospero": b"binary", "Prospero/../../evil": b"bad"})
    else:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive_file:
            good = tarfile.TarInfo("Prospero/Prospero")
            good.size = 6
            archive_file.addfile(good, io.BytesIO(b"binary"))
            evil = tarfile.TarInfo("../evil")
            evil.size = 3
            archive_file.addfile(evil, io.BytesIO(b"bad"))
        archive = buffer.getvalue()

    archive_path = tmp_path / archive_name()
    archive_path.write_bytes(archive)
    release = GithubLatestRelease.model_validate_json(
        release_payload("99.0.0", "https://example.com/update", len(archive))
    )
    version = release.directory_version()
    updater.update_info.state = UpdateStatus.downloaded
    updater.update_info.latest_release = release
    updater._install_version = version  # pyright: ignore[reportPrivateUsage]
    committed: list[str] = []
    monkeypatch.setattr("updater.commit_install", lambda value: committed.append(value) or True)
    monkeypatch.setattr("updater.restart_app", lambda: True)

    updater._install_worker(version, archive_path)  # pyright: ignore[reportPrivateUsage]

    assert pump_until(lambda: updater.update_info.error is not None)
    assert committed == []
    assert not (tmp_path / "evil").exists()

# endregion
