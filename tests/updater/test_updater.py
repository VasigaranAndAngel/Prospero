"""Tests for the updater, which now sits on top of the shared network client.

The installer is never actually launched: ``_run_installer`` is stubbed wherever a test lets a
download finish.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from arg_parser import args
from constants import APPLICATION_VERSION
from helpers.singleton_meta import SingletonMeta
from network import Downloaded, NetworkClient, NetworkError
from updater import GithubLatestRelease, Updater

Pump = Callable[[Callable[[], bool]], bool]

BAD_PAYLOAD: bytes = b'{"unexpected": true}'
"Valid JSON that does not match the GithubLatestRelease model."


def release_payload(tag: str, asset_url: str, asset_size: int) -> bytes:
    """Builds a GitHub release payload shaped like the real API response."""
    return json.dumps(
        {
            "tag_name": tag,
            "name": f"Prospero {tag}",
            "body": "notes",
            "assets": [
                {
                    "browser_download_url": asset_url,
                    "name": "ProsperoSetup.exe",
                    "label": None,
                    "state": "uploaded",
                    "content_type": "application/octet-stream",
                    "size": asset_size,
                    "digest": None,
                }
            ],
        }
    ).encode()


@pytest.fixture
def updater(monkeypatch: pytest.MonkeyPatch) -> Updater:
    """A fresh Updater wired to the fixture's NetworkClient."""
    monkeypatch.setattr(args, "update_domain", None)
    monkeypatch.delitem(SingletonMeta._instances, Updater, raising=False)  # pyright: ignore[reportPrivateUsage]
    return Updater()


@pytest.fixture(autouse=True)
def no_installer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Updater, "_run_installer", lambda self, path: None)  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]


@pytest.fixture(autouse=True)
def default_release_payload(http_server: Any) -> Any:  # pyright: ignore[reportAny, reportExplicitAny]
    """Keeps one test's release payload from deciding the next test's result."""
    http_server.release_payload = BAD_PAYLOAD
    return http_server  # pyright: ignore[reportAny]


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
    emitted: list[object] = []
    _ = updater.update_checked.connect(emitted.append)

    updater.check_update()

    assert len(emitted) == 1
    assert isinstance(emitted[0], NetworkError)


def test_offline_update_aborts(offline: NetworkClient, updater: Updater) -> None:  # pyright: ignore[reportUnusedParameter]
    states: list[Downloaded] = []
    started: list[int] = []
    _ = updater.downloaded.connect(states.append)
    _ = updater.download_started.connect(lambda: started.append(1))

    release = GithubLatestRelease.model_validate_json(
        release_payload("99.0.0", "https://example.com/x.exe", 10)
    )
    updater.update(release)

    assert started == [1]
    assert states[-1].aborted is True
    assert states[-1].completed is False


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
    # The server default payload does not match the model.
    NetworkClient.set_base_url("github", base_url)
    results: list[GithubLatestRelease | NetworkError] = []

    updater.get_latest_release(results.append)

    assert pump_until(lambda: len(results) == 1)
    assert isinstance(results[0], NetworkError)
    assert "Unexpected release payload" in results[0].error_str


def test_check_update_reports_newer_release(
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    base_url: str,
    http_server: Any,  # pyright: ignore[reportExplicitAny, reportAny]
    updater: Updater,
    pump_until: Pump,
) -> None:
    http_server.release_payload = release_payload("999.0.0", f"{base_url}/file/10", 10)
    NetworkClient.set_base_url("github", base_url)
    emitted: list[object] = []
    _ = updater.update_checked.connect(emitted.append)

    updater.check_update()

    assert pump_until(lambda: len(emitted) == 1)
    assert isinstance(emitted[0], GithubLatestRelease)


def test_check_update_reports_up_to_date(
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    base_url: str,
    http_server: Any,  # pyright: ignore[reportExplicitAny, reportAny]
    updater: Updater,
    pump_until: Pump,
) -> None:
    http_server.release_payload = release_payload(
        str(APPLICATION_VERSION.major), f"{base_url}/file/10", 10
    )
    NetworkClient.set_base_url("github", base_url)
    emitted: list[object] = []
    _ = updater.update_checked.connect(emitted.append)

    updater.check_update()

    assert pump_until(lambda: len(emitted) == 1)
    assert emitted == [None], "same major version should count as up to date"


# endregion


# region downloading


def test_update_downloads_installer(
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    base_url: str,
    file_size: int,
    updater: Updater,
    pump_until: Pump,
    tmp_path: Path,  # pyright: ignore[reportUnusedParameter]
) -> None:
    release = GithubLatestRelease.model_validate_json(
        release_payload("99.0.0", f"{base_url}/file/{file_size}", file_size)
    )
    states: list[Downloaded] = []
    _ = updater.downloaded.connect(states.append)

    updater.update(release)

    assert pump_until(lambda: any(s.completed for s in states)), "installer never downloaded"
    final = states[-1]
    assert final.completed is True
    assert final.downloaded_size == file_size
    assert final.file_path.exists()
    assert final.file_path.stat().st_size == file_size
    # The temporary .part file must not survive a completed download.
    assert not list(final.file_path.parent.glob("*.part"))


def test_second_update_is_ignored_while_one_runs(
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    base_url: str,
    file_size: int,
    updater: Updater,
    pump_until: Pump,
) -> None:
    release = GithubLatestRelease.model_validate_json(
        release_payload("99.0.0", f"{base_url}/slow/{file_size}", file_size)
    )
    started: list[int] = []
    states: list[Downloaded] = []
    _ = updater.download_started.connect(lambda: started.append(1))
    _ = updater.downloaded.connect(states.append)

    updater.update(release)
    updater.update(release)

    assert started == [1], "a second update should not start while one is in flight"
    assert pump_until(lambda: any(s.downloaded_size > 0 for s in states))
    updater.cancel_update()


def test_cancel_update_when_idle_does_nothing(updater: Updater) -> None:
    states: list[Downloaded] = []
    _ = updater.downloaded.connect(states.append)

    updater.cancel_update()

    assert states == []


def test_cancel_update_stops_in_flight_download(
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    base_url: str,
    file_size: int,
    updater: Updater,
    pump_until: Pump,
) -> None:
    release = GithubLatestRelease.model_validate_json(
        release_payload("99.0.0", f"{base_url}/slow/{file_size}", file_size)
    )
    states: list[Downloaded] = []
    _ = updater.downloaded.connect(states.append)

    updater.update(release)
    assert pump_until(lambda: any(s.downloaded_size > 0 for s in states)), "nothing arrived"
    updater.cancel_update()

    assert pump_until(lambda: any(s.aborted for s in states)), "cancel was never reported"
    assert not any(s.completed for s in states)
    assert updater._update_progress is False  # pyright: ignore[reportPrivateUsage]


# endregion
