"""Installs the optional modules this application can use.

The flow is always the same: resolve the name against the allowlist, pick the vetted wheel that fits
this interpreter, download it through the shared network client while reporting progress, verify its
SHA-256, then unpack it somewhere only this application looks at and teach the import finder about
it.

The index on PyPI is deliberately not consulted. Every wheel's filename, url and digest is pinned in
the allowlist, so a compromised index cannot talk this application into fetching something else.
Pointing at a mirror instead is done with a base url override on the shared network client, which
swaps only the origin of the pinned url.

Progress is reported with :class:`network.Downloaded`, the same type the updater uses, so one
progress widget can serve both.
"""

import logging
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Final

from packaging.tags import sys_tags
from PySide6.QtCore import QObject, Signal

from arg_parser import args
from helpers import SingletonQObjectMeta
from network import Downloaded, NetworkClient

from ._allowlist import ALLOWLIST, AllowedPackage, PackageError, get_allowed, select_wheel
from ._finder import ModuleFinder
from ._storage import (
    InstalledPackage,
    cache_dir,
    extract_wheel,
    module_dir,
    modules_root,
    new_record,
    read_index,
    verify_sha256,
    write_index,
)

logger = logging.getLogger(__name__)

PYPI_SERVICE: Final[str] = "pypi"
"Service name a base url override for the download host would be registered under."


class PackageManager(QObject, metaclass=SingletonQObjectMeta):
    """Installs, tracks and removes the allowlisted optional modules.

    Inherits ``QObject``, so the first instantiation must happen after a ``QApplication`` exists.
    """

    install_started: Signal = Signal(str)
    "Emitted with the package name as an install begins."
    download_progress: Signal = Signal(Downloaded)
    "Emitted while the wheel downloads. Same shape the updater reports."
    install_finished: Signal = Signal(str)
    "Emitted with the package name once the module is installed and importable."
    install_failed: Signal = Signal(str, object)
    "Emitted with the package name and the PackageError that stopped it."
    installed_changed: Signal = Signal()
    "Emitted whenever the set of installed modules changes."

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._root: Path = modules_root()
        self._index: dict[str, InstalledPackage] = read_index(self._root)
        self._finder: ModuleFinder = ModuleFinder()
        self._network: NetworkClient = NetworkClient()
        self._sweep()
        self.activate()

    # region queries

    def available(self) -> list[AllowedPackage]:
        """Every package this application is willing to install."""
        return list(ALLOWLIST.values())

    def installed(self) -> dict[str, InstalledPackage]:
        """The install index, keyed by canonical package name."""
        return dict(self._index)

    def is_installed(self, name: str, version: str | None = None) -> bool:
        """Whether an allowed package is installed, optionally at a given version."""
        try:
            package = get_allowed(name)
        except PackageError:
            return False
        record = self._index.get(package.canonical_name)
        if record is None:
            return False
        return version is None or record.version == version

    def finder(self) -> ModuleFinder:
        """The import finder, so callers can see what is currently importable."""
        return self._finder

    def activate(self) -> None:
        """Points the import finder at everything currently installed."""
        for record in self._index.values():
            directory = record.resolve(self._root)
            if directory.is_dir():
                self._finder.register(record.import_name, directory)
            else:
                logger.warning("Installed module %s is missing from %s", record.name, directory)

    # endregion

    # region install

    def install(self, name: str, callback: Callable[[Downloaded], None] | None = None) -> None:
        """Installs an allowlisted package, downloading the wheel if needed.

        Reports through the signals on this object. A package already installed at the pinned
        version is a no-op, so this is safe to call repeatedly.

        Args:
            name (str): Distribution or import name, e.g. ``pillow`` or ``PIL``.
            callback (Callable | None): Called with each download progress update.
        """
        self.install_started.emit(name)
        try:
            package = get_allowed(name)
            wheel = select_wheel(package)
            if wheel is None:
                raise PackageError(
                    f"No vetted {package.name} {package.version} wheel matches this "
                    + f"interpreter ({_interpreter_tag()}).",
                    name,
                )

            if self._is_current(package, wheel.sha256):
                logger.debug("%s %s is already installed", package.name, package.version)
                self.activate()
                self.install_finished.emit(package.name)
                return

            if args.offline:
                cached = cache_dir(self._root) / wheel.filename
                if not cached.is_file():
                    raise PackageError(
                        f"Offline, and no cached {wheel.filename} to install from.", name
                    )
                logger.debug("Installing %s from cached wheel %s", package.name, cached)
                self._install_from(package, wheel.filename, cached, wheel.sha256)
                return

            url = self._network.mirror(PYPI_SERVICE, wheel.url)
            self._download_then_install(package, wheel.filename, url, wheel.sha256, callback)
        except PackageError as e:
            logger.warning("Cannot install %s: %s", name, e.error_str)
            self.install_failed.emit(name, e)

    def install_local(self, name: str, wheel: Path) -> None:
        """Installs an allowlisted package from a wheel already on disk.

        The wheel still has to match the pinned digest, so this accepts a previously cached or
        manually obtained copy but not an arbitrary build.

        Args:
            name (str): Distribution or import name.
            wheel (Path): The wheel file to install.
        """
        self.install_started.emit(name)
        try:
            package = get_allowed(name)
            wheel_meta = select_wheel(package)
            if wheel_meta is None:
                raise PackageError(
                    f"No vetted {package.name} {package.version} wheel matches this interpreter.",
                    name,
                )
            if not wheel.is_file():
                raise PackageError(f"No such wheel file: {wheel}", name)
            self._install_from(package, wheel.name, wheel, wheel_meta.sha256)
        except PackageError as e:
            logger.warning("Cannot install %s from %s: %s", name, wheel, e.error_str)
            self.install_failed.emit(name, e)

    def _download_then_install(
        self,
        package: AllowedPackage,
        filename: str,
        url: str,
        sha256: str,
        callback: Callable[[Downloaded], None] | None,
    ) -> None:
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"{package.name}-"))
        target = tmp_dir / filename

        def _on_state(state: Downloaded) -> None:
            self.download_progress.emit(state)
            if callback is not None:
                callback(state)
            if state.aborted:
                _ = self._discard(tmp_dir)
                self._fail(package.name, f"Download of {filename} did not finish.")
            elif state.completed:
                try:
                    self._install_from(package, filename, state.file_path, sha256)
                except PackageError as e:
                    # Cannot let this escape, it is raised inside a signal callback.
                    self._fail(package.name, e.error_str)
                finally:
                    _ = self._discard(tmp_dir)

        self._network.download(url, target, _on_state)

    def _install_from(
        self, package: AllowedPackage, filename: str, wheel: Path, sha256: str
    ) -> None:
        """Verifies a wheel, unpacks it, records it and makes it importable."""
        actual = verify_sha256(wheel, sha256, package.name)

        destination = module_dir(package.canonical_name, package.version, self._root)
        staging = destination.with_name(f"{destination.name}.staging")
        _ = self._discard(staging)

        try:
            written = extract_wheel(wheel, staging, package.allowed_top_level, package.name)
            if destination.is_dir():
                _ = shutil.rmtree(destination)
            _ = staging.replace(destination)
        except OSError as e:
            _ = self._discard(staging)
            raise PackageError(f"Could not unpack {filename}: {e}", package.name) from e
        except PackageError:
            _ = self._discard(staging)
            raise

        importable = tuple(n for n in written if not n.endswith(".dist-info"))
        self._index[package.canonical_name] = new_record(
            package.canonical_name,
            package.version,
            package.import_name,
            actual,
            importable,
            destination,
        )
        write_index(self._index, self._root)
        self._finder.register(package.import_name, destination)
        self._cache(wheel, filename)

        logger.info("Installed %s %s to %s", package.name, package.version, destination)
        self.installed_changed.emit()
        self.install_finished.emit(package.name)

    def _cache(self, wheel: Path, filename: str) -> None:
        """Keeps a copy of a verified wheel so it can be reinstalled offline."""
        target = cache_dir(self._root) / filename
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            _ = shutil.copy2(wheel, target)
        except OSError as e:
            logger.warning("Could not cache wheel %s: %s", filename, e)

    def _retire(self, directory: Path) -> bool:
        """Renames a module directory aside then deletes it. True if it is gone.

        Renaming first means the import finder stops resolving the module even when the files cannot
        be deleted, which is the normal outcome on Windows once the module has been imported.
        """
        if not directory.is_dir():
            return True
        aside = directory.with_name(f"{directory.name}.removing")
        _ = self._discard(aside)
        try:
            _ = directory.replace(aside)
        except OSError as e:
            logger.warning("Could not set aside %s: %s", directory, e)
            return not directory.is_dir()
        return self._discard(aside)

    def _sweep(self) -> None:
        """Deletes leftovers from a previous uninstall that could not delete."""
        if not self._root.is_dir():
            return
        for leftover in self._root.glob("*.removing"):
            logger.debug("Sweeping %s", leftover)
            _ = self._discard(leftover)

    def _discard(self, path: Path) -> bool:
        """Deletes a file or directory. Returns False when it could not be removed."""
        if path.is_dir():
            _ = shutil.rmtree(path, ignore_errors=True)
        elif path.is_file():
            try:
                _ = path.unlink(missing_ok=True)
            except OSError as e:
                logger.warning("Could not remove %s: %s", path, e)
                return False
        return not path.exists()

    def _fail(self, name: str, reason: str) -> None:
        logger.warning("Install of %s failed: %s", name, reason)
        self.install_failed.emit(name, PackageError(reason, name))

    def _is_current(self, package: AllowedPackage, sha256: str) -> bool:
        record = self._index.get(package.canonical_name)
        if record is None or record.version != package.version or record.sha256 != sha256:
            return False
        return record.resolve(self._root).is_dir()

    # endregion

    # region remove

    def uninstall(self, name: str) -> bool:
        """Stops an installed module being importable and tries to delete it.

        The directory is renamed out of the way first, so the module stops resolving immediately.
        Windows keeps a loaded module's files locked, so when the module is already imported the
        files usually survive until the next start; that is why the return value reports whether
        they are gone.

        Args:
            name (str): Distribution or import name.

        Returns:
            bool: Whether the files were actually removed from disk.
        """
        try:
            package = get_allowed(name)
        except PackageError:
            return False

        record = self._index.pop(package.canonical_name, None)
        if record is None:
            return False

        self._finder.unregister(record.import_name)
        gone = self._retire(record.resolve(self._root))
        write_index(self._index, self._root)

        if gone:
            logger.info("Removed %s", package.name)
        else:
            logger.info(
                "Removed %s from the index, but its files stay until the next start "
                + "because the module is still loaded",
                package.name,
            )
        self.installed_changed.emit()
        return gone

    # endregion


def _interpreter_tag() -> str:
    return str(next(iter(sys_tags()), "unknown"))
