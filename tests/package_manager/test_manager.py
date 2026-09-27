"""Tests for the installer that ties the allowlist, storage and finder together."""

import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest
from _fakes import (  # pyright: ignore[reportImplicitRelativeImport]
    WHEEL_NAME,
    build_wheel,
    patch_wheel,
)
from PySide6.QtCore import QCoreApplication

from arg_parser import args
from network import Downloaded, NetworkClient
from package_manager import PackageError, PackageManager
from package_manager._storage import index_path, read_index

Pump = Callable[[Callable[[], bool]], bool]


@pytest.fixture
def failures(manager: PackageManager) -> list[tuple[str, PackageError]]:
    """Collects install_failed emissions."""
    seen: list[tuple[str, PackageError]] = []
    _ = manager.install_failed.connect(lambda name, error: seen.append((name, error)))  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    return seen


@pytest.fixture
def successes(manager: PackageManager) -> list[str]:
    """Collects install_finished emissions."""
    seen: list[str] = []
    _ = manager.install_finished.connect(seen.append)
    return seen


def forget_pil() -> None:
    """Drops PIL from sys.modules so a test can import it again."""
    for name in list(sys.modules):
        if name == "PIL" or name.startswith("PIL."):
            del sys.modules[name]


# region queries


def test_pillow_is_offered(manager: PackageManager) -> None:
    assert [p.name for p in manager.available()] == ["pillow"]


def test_nothing_is_installed_to_start_with(manager: PackageManager) -> None:
    assert manager.installed() == {}
    assert manager.is_installed("pillow") is False
    assert manager.finder().import_names == ()


def test_is_installed_accepts_import_name(manager: PackageManager) -> None:
    assert manager.is_installed("PIL") is False


def test_is_installed_is_false_for_unknown_package(manager: PackageManager) -> None:
    assert manager.is_installed("requests") is False


# endregion


# region installing from a local wheel


def test_install_unpacks_and_records(
    manager: PackageManager, allow_local: Path, successes: list[str]
) -> None:
    manager.install_local("pillow", allow_local)

    assert successes == ["pillow"]
    assert manager.is_installed("pillow") is True
    record = manager.installed()["pillow"]
    assert record.version == "12.3.0"
    assert record.import_name == "PIL"
    assert record.top_level == ("PIL",)
    assert (Path(record.directory) / "PIL" / "__init__.py").is_file()


def test_install_makes_the_module_importable(manager: PackageManager, allow_local: Path) -> None:
    manager.install_local("pillow", allow_local)
    forget_pil()
    try:
        module: ModuleType = cast(ModuleType, __import__("PIL"))

        assert module.__file__ is not None
        assert Path(module.__file__).is_relative_to(manager.installed()["pillow"].directory)
    finally:
        forget_pil()


def test_install_registers_with_the_finder(manager: PackageManager, allow_local: Path) -> None:
    manager.install_local("pillow", allow_local)

    assert manager.finder().import_names == ("PIL",)
    assert manager.finder() in sys.meta_path


def test_install_writes_the_index(manager: PackageManager, allow_local: Path) -> None:
    manager.install_local("pillow", allow_local)

    assert index_path().is_file()
    assert "pillow" in read_index()


def test_install_caches_the_wheel_for_offline_reuse(
    manager: PackageManager, allow_local: Path
) -> None:
    manager.install_local("pillow", allow_local)

    assert (index_path().parent / "cache" / WHEEL_NAME).is_file()


def test_install_announces_itself(manager: PackageManager, allow_local: Path) -> None:
    started: list[str] = []
    _ = manager.install_started.connect(started.append)

    manager.install_local("pillow", allow_local)

    assert started == ["pillow"]


def test_install_notifies_of_the_change(manager: PackageManager, allow_local: Path) -> None:
    changed: list[int] = []
    _ = manager.installed_changed.connect(lambda: changed.append(1))

    manager.install_local("pillow", allow_local)

    assert changed == [1]


def test_install_reuses_an_existing_directory(
    manager: PackageManager, allow_local: Path, successes: list[str]
) -> None:
    manager.install_local("pillow", allow_local)
    successes.clear()

    manager.install_local("pillow", allow_local)

    assert successes == ["pillow"], "a second install should still succeed"
    assert manager.is_installed("pillow") is True


# endregion


# region refusals


def test_unknown_package_is_refused(
    manager: PackageManager, allow_local: Path, failures: list[tuple[str, PackageError]]
) -> None:
    manager.install_local("requests", allow_local)

    assert [name for name, _ in failures] == ["requests"]
    assert "not an installable module" in failures[0][1].error_str


def test_missing_wheel_file_is_refused(
    manager: PackageManager, allow_local: Path, failures: list[tuple[str, PackageError]]
) -> None:
    manager.install_local("pillow", allow_local.parent / "nope.whl")

    assert "No such wheel file" in failures[0][1].error_str


def test_tampered_wheel_is_refused(
    manager: PackageManager,
    fake_wheel: Path,
    monkeypatch: pytest.MonkeyPatch,
    failures: list[tuple[str, PackageError]],
) -> None:
    _ = patch_wheel(monkeypatch, fake_wheel)
    data = bytearray(fake_wheel.read_bytes())
    data[len(data) // 2] ^= 0xFF
    tampered = fake_wheel.parent / WHEEL_NAME
    _ = tampered.write_bytes(bytes(data))

    manager.install_local("pillow", tampered)

    assert "Checksum mismatch" in failures[0][1].error_str
    assert manager.is_installed("pillow") is False


def test_wheel_with_an_unexpected_payload_is_refused(
    manager: PackageManager,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failures: list[tuple[str, PackageError]],
) -> None:
    wheel = build_wheel(tmp_path / "evil" / WHEEL_NAME, {"evil/thing.py": b"pwned"})
    _ = patch_wheel(monkeypatch, wheel)

    manager.install_local("pillow", wheel)

    assert "unexpected top level entry" in failures[0][1].error_str
    assert manager.is_installed("pillow") is False


def test_no_staging_directory_is_left_behind(
    manager: PackageManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wheel = build_wheel(tmp_path / "evil" / WHEEL_NAME, {"evil/thing.py": b"pwned"})
    _ = patch_wheel(monkeypatch, wheel)

    manager.install_local("pillow", wheel)

    root = index_path().parent
    assert not list(root.glob("*.staging"))


# endregion


# region installing over the network


def test_install_downloads_then_unpacks(
    manager: PackageManager,
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    base_url: str,
    http_server: Any,  # pyright: ignore[reportAny, reportExplicitAny]
    fake_wheel: Path,
    monkeypatch: pytest.MonkeyPatch,
    successes: list[str],
    pump_until: Pump,
) -> None:
    """Serve the synthetic wheel locally and let the real download path run."""
    http_server.wheel_bytes = fake_wheel.read_bytes()
    _ = patch_wheel(monkeypatch, fake_wheel, url=f"{base_url}/packages/{WHEEL_NAME}")
    NetworkClient.set_base_url("pypi", base_url)
    progress: list[Downloaded] = []
    _ = manager.download_progress.connect(progress.append)

    manager.install("pillow")

    assert pump_until(lambda: bool(successes)), "install never finished"
    assert manager.is_installed("pillow") is True
    assert progress, "no download progress was reported"
    assert progress[-1].completed is True
    record = manager.installed()["pillow"]
    assert (Path(record.directory) / "PIL" / "__init__.py").is_file()


def test_downloaded_wheel_is_verified_before_unpacking(
    manager: PackageManager,
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    base_url: str,
    http_server: Any,  # pyright: ignore[reportExplicitAny, reportAny]
    fake_wheel: Path,
    monkeypatch: pytest.MonkeyPatch,
    failures: list[tuple[str, PackageError]],
    pump_until: Pump,
) -> None:
    """A mirror serving different bytes must not get to write anything."""
    http_server.wheel_bytes = fake_wheel.read_bytes() + b"tampered"
    _ = patch_wheel(monkeypatch, fake_wheel, url=f"{base_url}/packages/{WHEEL_NAME}")
    NetworkClient.set_base_url("pypi", base_url)

    manager.install("pillow")

    assert pump_until(lambda: bool(failures)), "the bad wheel was not rejected"
    assert "Checksum mismatch" in failures[0][1].error_str
    assert manager.is_installed("pillow") is False


def test_offline_without_a_cache_is_refused(
    manager: PackageManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[str, PackageError]] = []
    _ = manager.install_failed.connect(lambda name, error: seen.append((name, error)))  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    monkeypatch.setattr(args, "offline", True)

    manager.install("pillow")

    assert "Offline" in seen[0][1].error_str
    assert manager.is_installed("pillow") is False


def test_offline_installs_from_the_cache(
    manager: PackageManager,
    allow_local: Path,
    monkeypatch: pytest.MonkeyPatch,
    successes: list[str],
) -> None:
    manager.install_local("pillow", allow_local)
    _ = manager.uninstall("pillow")
    successes.clear()
    monkeypatch.setattr(args, "offline", True)

    manager.install("pillow")

    assert successes == ["pillow"]
    assert manager.is_installed("pillow") is True


def test_install_is_a_no_op_when_current(
    manager: PackageManager, allow_local: Path, successes: list[str]
) -> None:
    manager.install_local("pillow", allow_local)
    successes.clear()

    manager.install("pillow")

    assert successes == ["pillow"]
    assert manager.is_installed("pillow") is True


# endregion


# region removing


def test_uninstall_forgets_and_removes(manager: PackageManager, allow_local: Path) -> None:
    manager.install_local("pillow", allow_local)
    record = manager.installed()["pillow"]
    forget_pil()

    assert manager.uninstall("pillow") is True
    assert manager.is_installed("pillow") is False
    assert manager.finder().import_names == ()
    assert not Path(record.directory).exists()


def test_uninstall_clears_the_index(manager: PackageManager, allow_local: Path) -> None:
    manager.install_local("pillow", allow_local)

    _ = manager.uninstall("pillow")

    assert read_index() == {}


def test_uninstall_of_something_absent_returns_false(manager: PackageManager) -> None:
    assert manager.uninstall("pillow") is False


def test_uninstall_of_unknown_package_returns_false(manager: PackageManager) -> None:
    assert manager.uninstall("requests") is False


def test_reinstall_after_uninstall_works(
    manager: PackageManager, allow_local: Path, successes: list[str]
) -> None:
    manager.install_local("pillow", allow_local)
    _ = manager.uninstall("pillow")
    successes.clear()

    manager.install_local("pillow", allow_local)

    assert successes == ["pillow"]
    assert manager.is_installed("pillow") is True


def test_a_new_manager_picks_up_an_existing_install(
    qt_app: QCoreApplication,  # pyright: ignore[reportUnusedParameter]
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    modules_root: Path,  # pyright: ignore[reportUnusedParameter]
    allow_local: Path,
    monkeypatch: pytest.MonkeyPatch,  # pyright: ignore[reportUnusedParameter]
) -> None:
    """The index has to survive a restart, otherwise the module is forgotten."""
    from helpers.singleton_meta import SingletonMeta

    _ = SingletonMeta._instances.pop(PackageManager, None)  # pyright: ignore[reportPrivateUsage]
    first = PackageManager()
    first.install_local("pillow", allow_local)
    assert first.is_installed("pillow") is True

    _ = SingletonMeta._instances.pop(PackageManager, None)  # pyright: ignore[reportPrivateUsage]
    second = PackageManager()

    assert second.is_installed("pillow") is True
    assert second.finder().import_names == ("PIL",)
    for name in second.finder().import_names:
        second.finder().unregister(name)
    _ = SingletonMeta._instances.pop(PackageManager, None)  # pyright: ignore[reportPrivateUsage]


# endregion
