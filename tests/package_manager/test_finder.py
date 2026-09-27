"""Tests for the import finder that makes installed modules resolvable.

The point of using a meta path finder instead of ``sys.path`` is that it answers for the names it
was given and stays out of the way otherwise. Both halves of that are checked here.
"""

import sys
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

from package_manager import ModuleFinder

REGISTERED: str = "demopkg"


@pytest.fixture
def package_dir(tmp_path: Path) -> Path:
    """A minimal importable package on disk."""
    root = tmp_path / "demopkg-1.0.0"
    (root / REGISTERED).mkdir(parents=True)
    _ = (root / REGISTERED / "__init__.py").write_text("VALUE = 42\n", encoding="utf-8")
    _ = (root / REGISTERED / "sub.py").write_text("NAME = 'sub'\n", encoding="utf-8")
    return root


@pytest.fixture
def finder() -> ModuleFinder:
    return ModuleFinder()


# region registration


def test_starts_out_inactive(finder: ModuleFinder) -> None:
    assert finder.import_names == ()
    assert finder not in sys.meta_path


def test_registering_inserts_into_meta_path(finder: ModuleFinder, package_dir: Path) -> None:
    before = list(sys.meta_path)

    finder.register(REGISTERED, package_dir)

    assert finder in sys.meta_path
    assert sys.meta_path[0] is finder
    assert len(sys.meta_path) == len(before) + 1


def test_unregistering_restores_meta_path(finder: ModuleFinder, package_dir: Path) -> None:
    before = list(sys.meta_path)
    finder.register(REGISTERED, package_dir)

    finder.unregister(REGISTERED)

    assert sys.meta_path == before
    assert finder.import_names == ()


def test_registering_twice_does_not_double_insert(finder: ModuleFinder, package_dir: Path) -> None:
    finder.register(REGISTERED, package_dir)
    count = sys.meta_path.count(finder)

    finder.register(REGISTERED, package_dir)

    assert sys.meta_path.count(finder) == count


def test_unregistering_unknown_name_is_harmless(finder: ModuleFinder) -> None:
    finder.unregister("never-registered")

    assert finder not in sys.meta_path


def test_root_for_reports_the_directory(finder: ModuleFinder, package_dir: Path) -> None:
    finder.register(REGISTERED, package_dir)

    assert finder.root_for(REGISTERED) == package_dir
    assert finder.root_for("other") is None


# endregion


# region resolution


def test_registered_name_resolves(finder: ModuleFinder, package_dir: Path) -> None:
    finder.register(REGISTERED, package_dir)

    spec = finder.find_spec(REGISTERED)

    assert spec is not None
    assert spec.origin is not None
    assert spec.origin.endswith("__init__.py")
    assert spec.submodule_search_locations is not None


def test_unregistered_name_is_declined(finder: ModuleFinder, package_dir: Path) -> None:
    finder.register(REGISTERED, package_dir)

    assert finder.find_spec("json") is None
    assert finder.find_spec("numpy") is None


def test_submodule_lookup_is_left_to_the_path_based_finder(
    finder: ModuleFinder, package_dir: Path
) -> None:
    """A non-None path means we are inside a package, so stay out of it."""
    finder.register(REGISTERED, package_dir)

    assert finder.find_spec(f"{REGISTERED}.sub", path=[str(package_dir)]) is None


def test_missing_package_directory_is_declined(finder: ModuleFinder, tmp_path: Path) -> None:
    finder.register(REGISTERED, tmp_path / "does-not-exist")

    assert finder.find_spec(REGISTERED) is None


def test_namespace_package_without_init_resolves(finder: ModuleFinder, tmp_path: Path) -> None:
    root = tmp_path / "ns-1.0.0"
    package = root / "nspkg"
    package.mkdir(parents=True)
    finder.register("nspkg", root)

    spec = finder.find_spec("nspkg")

    assert spec is not None
    # A namespace package has no origin file, only a search location.
    assert spec.origin is None
    assert spec.submodule_search_locations == [str(package)]


def test_a_real_import_works_end_to_end(finder: ModuleFinder, package_dir: Path) -> None:
    """The whole point: an unregistered interpreter can import the module."""
    finder.register(REGISTERED, package_dir)
    try:
        module = cast(ModuleType, __import__(REGISTERED))

        assert module.VALUE == 42  # pyright: ignore[reportAny]
        assert module.__file__ is not None
        assert str(package_dir) in module.__file__
        from demopkg import (  # pyright: ignore[reportMissingImports]
            sub,  # type: ignore[import-not-found]  # pyright: ignore[reportUnknownVariableType]
        )

        assert sub.NAME == "sub"  # pyright: ignore[reportUnknownMemberType]
    finally:
        for name in list(sys.modules):
            if name == REGISTERED or name.startswith(f"{REGISTERED}."):
                del sys.modules[name]
        finder.unregister(REGISTERED)


# endregion
