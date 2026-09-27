"""Fixtures for the optional module installer.

Tests build tiny synthetic wheels rather than using a real one, so they run fast and stay hermetic.
A synthetic wheel is made acceptable to the allowlist by pointing Pillow's wheel entry at it, with
its real digest.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from _fakes import (  # pyright: ignore[reportImplicitRelativeImport]
    WHEEL_NAME,
    build_wheel,
    patch_wheel,
)
from PySide6.QtCore import QCoreApplication

from arg_parser import args
from helpers.singleton_meta import SingletonMeta
from network import NetworkClient
from package_manager import PackageManager


@pytest.fixture
def modules_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirects the install root into a temporary directory."""
    root = tmp_path / "modules"
    monkeypatch.setenv("PROSPERO_MODULES_PATH", str(root))
    return root


@pytest.fixture
def manager(
    qt_app: QCoreApplication,  # pyright: ignore[reportUnusedParameter]
    client: NetworkClient,  # pyright: ignore[reportUnusedParameter]
    modules_root: Path,  # pyright: ignore[reportUnusedParameter]
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[PackageManager]:
    """A PackageManager rooted in a temporary directory, with no leftover state.

    The singleton is dropped on the way out as well as on the way in. Otherwise a later test that
    constructs PackageManager without this fixture would get this one, still pointing at a temporary
    directory that has since been deleted.
    """
    monkeypatch.setattr(args, "offline", False)
    _drop_singleton()
    instance = PackageManager()
    try:
        yield instance
    finally:
        for name in instance.finder().import_names:
            instance.finder().unregister(name)
        _drop_singleton()


def _drop_singleton() -> None:
    _ = SingletonMeta._instances.pop(PackageManager, None)  # pyright: ignore[reportPrivateUsage]


@pytest.fixture
def fake_wheel(tmp_path: Path) -> Path:
    """A small synthetic wheel named the way the allowlist expects."""
    return build_wheel(tmp_path / "wheels" / WHEEL_NAME)


@pytest.fixture
def allow_local(fake_wheel: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Makes the synthetic wheel acceptable to the allowlist."""
    _ = patch_wheel(monkeypatch, fake_wheel)
    return fake_wheel
