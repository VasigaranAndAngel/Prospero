"""Makes an installed module importable without touching ``sys.path``.

Appending to ``sys.path`` is the usual way to do this, but it is global, it is searched for every
import in the process, and nothing ever un-sorts it. A ``sys.meta_path`` finder answers only for the
exact top level names that were registered with it and returns ``None`` for everything else, so the
rest of the import system behaves exactly as it did before.
"""

import logging
import sys
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec
from importlib.util import spec_from_file_location
from pathlib import Path
from typing import Final, override

logger = logging.getLogger(__name__)

INIT_NAME: Final[str] = "__init__.py"


class ModuleFinder(MetaPathFinder):
    """Resolves registered import names against directories we control.

    Inserted at the front of ``sys.meta_path`` only while something is registered, and removed again
    as soon as nothing is. Submodules of a registered package are left to the normal path based
    lookup, which works because the parent's ``__path__`` already points inside our directory.
    """

    def __init__(self) -> None:
        self._roots: dict[str, Path] = {}

    @property
    def import_names(self) -> tuple[str, ...]:
        """Top level names this finder currently answers for."""
        return tuple(sorted(self._roots))

    def root_for(self, import_name: str) -> Path | None:
        """Directory backing an import name, if it is registered."""
        return self._roots.get(import_name)

    def register(self, import_name: str, directory: Path) -> None:
        """Makes ``import_name`` resolve from ``directory``.

        Args:
            import_name (str): Top level name, e.g. ``PIL``.
            directory (Path): Directory the package was unpacked into.
        """
        self._roots[import_name] = directory
        logger.debug("Finder registered %s from %s", import_name, directory)
        self._sync()

    def unregister(self, import_name: str) -> None:
        """Stops resolving ``import_name``.

        Already imported modules stay in ``sys.modules``, so this takes effect for the next process
        rather than the current one.
        """
        if self._roots.pop(import_name, None) is not None:
            logger.debug("Finder unregistered %s", import_name)
            self._sync()

    @override
    def find_spec(
        self,
        fullname: str,
        path: object = None,
        target: object = None,
    ) -> ModuleSpec | None:
        """Resolves a top level import against the registered directories."""
        if path is not None:
            return None
        root = self._roots.get(fullname)
        if root is None:
            return None

        package = root / fullname
        if not package.is_dir():
            logger.warning("Registered import %s is missing from %s", fullname, root)
            return None

        init = package / INIT_NAME
        if init.is_file():
            return spec_from_file_location(
                fullname, init, submodule_search_locations=[str(package)]
            )
        # A directory with no __init__.py is a namespace style package.
        spec = ModuleSpec(fullname, None, is_package=True)
        spec.submodule_search_locations = [str(package)]
        return spec

    def _sync(self) -> None:
        """Keeps ``sys.meta_path`` in step with what is registered."""
        if self._roots:
            if self not in sys.meta_path:
                sys.meta_path.insert(0, self)
        elif self in sys.meta_path:
            sys.meta_path.remove(self)
            logger.debug("Finder removed from sys.meta_path")
