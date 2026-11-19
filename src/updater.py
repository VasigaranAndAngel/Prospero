import fnmatch
import logging
import os
import posixpath
import shutil
import sys
import tarfile
import tempfile
import threading
import uuid
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import Enum, auto
from functools import partial
from hashlib import file_digest
from pathlib import Path, PurePosixPath
from typing import IO, ClassVar, Final, Literal, TypeVar

from packaging.version import Version
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QWidget

from arg_parser import args
from constants import APPLICATION_NAME, APPLICATION_VERSION, REPO_NAME, REPO_OWNER
from helpers import SingletonQObjectMeta
from network import Downloaded, NetworkClient, NetworkError
from platform_specific.paths import (
    current_version,
    is_installed_layout,
    version_dir,
    versions_dir,
)
from platform_specific.updater import (
    APP_EXECUTABLE_NAME,
    FILE_MATCH_PATS,
    cleanup_old_versions,
    commit_install,
    restart_app,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

GITHUB_SERVICE: Final[str] = "github"
"Service name used to register a base url override for the GitHub API."

DEFAULT_GITHUB_DOMAIN: Final[str] = "https://api.github.com"

_CHUNK_SIZE: Final[int] = 1024 * 1024
"Extraction / progress chunk size."

__all__ = [
    "Downloaded",
    "GithubLatestRelease",
    "InstallProgress",
    "NetworkError",
    "UpdateInfo",
    "UpdateStatus",
    "Updater",
]


@dataclass
class _GithubAsset(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    browser_download_url: str
    name: str
    label: str | None
    state: Literal["uploaded", "open"]
    content_type: str
    size: int
    digest: str | None = None


class GithubLatestRelease(BaseModel):
    "A model to validate latest release from github"

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    tag_name: str
    name: str
    body: str | None
    assets: list[_GithubAsset]

    @field_validator("tag_name")
    @classmethod
    def _validate_tag_name(cls, value: str) -> str:
        _ = Version(value)
        return value

    def get_version(self) -> Version:
        return Version(self.tag_name)

    def directory_version(self) -> str:
        """Version string used for the on-disk directory name."""
        return self.tag_name.removeprefix("v")


class UpdateStatus(Enum):
    none = auto()
    update_checking = auto()
    update_checked = auto()
    download_started = auto()
    downloading = auto()
    downloaded = auto()
    download_aborted = auto()
    installation_started = auto()
    installing = auto()
    installed = auto()
    installation_queue = auto()
    restart_queue = auto()


@dataclass
class InstallProgress:
    total: float
    installed: float
    completed: bool

    @property
    def ratio(self) -> float:
        if self.total <= 0:
            return 0.0
        return min(self.installed / self.total, 1.0)


@dataclass
class UpdateInfo:
    "Single object which contains all UI needed info and will be used over an entire update process."

    state: UpdateStatus
    update_available: bool | None = None
    latest_release: GithubLatestRelease | None = None
    download_progress: Downloaded | None = None
    install_progress: InstallProgress | None = None
    error: Exception | NetworkError | str | None = None
    domain: str | None = None


class _InstallCancelled(Exception):
    pass


def _safe_member(name: str) -> PurePosixPath:
    """Normalize and validate an archive member name."""
    normalized = PurePosixPath(name.replace("\\", "/"))
    if normalized.is_absolute() or (normalized.parts and normalized.parts[0].endswith(":")):
        raise ValueError(f"Absolute path in update archive: {name!r}")
    parts = tuple(part for part in normalized.parts if part not in {"", "."})
    if not parts or any(part == ".." or ":" in part for part in parts):
        raise ValueError(f"Unsafe path in update archive: {name!r}")
    return PurePosixPath(*parts)


def _safe_link_target(member: PurePosixPath, linkname: str) -> str:
    """Validate and normalize a relative symlink target inside the app tree."""
    if not linkname or "\x00" in linkname:
        raise ValueError(f"Unsafe link target in update archive: {linkname!r}")

    link = PurePosixPath(linkname.replace("\\", "/"))
    if link.is_absolute() or (link.parts and link.parts[0].endswith(":")):
        raise ValueError(f"Absolute link target in update archive: {linkname!r}")
    if any(":" in part for part in link.parts):
        raise ValueError(f"Unsafe link target in update archive: {linkname!r}")

    normalized = PurePosixPath(posixpath.normpath(str(member.parent / link)))
    app_root = APPLICATION_NAME.title()
    if not normalized.parts or normalized.parts[0] != app_root:
        raise ValueError(f"Link target escapes the app directory: {linkname!r}")
    return posixpath.relpath(str(normalized), str(member.parent))


def _matching_assets(assets: list[_GithubAsset]) -> tuple[_GithubAsset, ...]:
    """Return assets for the first platform pattern that matches, preferring XZ archives."""
    for pattern in FILE_MATCH_PATS:
        matches = tuple(asset for asset in assets if fnmatch.fnmatch(asset.name, pattern))
        if matches:
            return matches
    return ()


def _can_self_update() -> bool:
    """Only a frozen build in the versioned install layout can replace itself and restart."""
    return getattr(sys, "frozen", False) and is_installed_layout()


def _selected_members(
    members: list[tuple[T, PurePosixPath]],
) -> list[tuple[T, PurePosixPath]]:
    """Select the ``Prospero/`` tree, or wrap a flat archive in one."""
    if any(path.parts[0] == APPLICATION_NAME.title() for _, path in members):
        return [
            (member, path) for member, path in members if path.parts[0] == APPLICATION_NAME.title()
        ]
    return [(member, PurePosixPath(APPLICATION_NAME.title()) / path) for member, path in members]


class Updater(QObject, metaclass=SingletonQObjectMeta):
    """This is a singleton object which can check for new version of application and download and
    install it. Since it is inherited QObject this class should be initialized after a QApplication
    instance is created.

    Networking is delegated to :class:`network.NetworkClient`. Installation extracts an update
    archive into a new versioned directory, then asks the platform layer to activate it and
    restart the app.
    """

    GithubFetchError: type[NetworkError] = NetworkError
    "Kept for callers that test for it by name. NetworkError is the type itself."

    update_info_updated: Signal = Signal(UpdateInfo)
    """Emitted with UpdateInfo with the current state of update process."""

    _install_event: Signal = Signal()
    "Internal: wakes the main thread after the installer worker changes UpdateInfo."

    _install_finished: Signal = Signal(bool)
    "Internal: worker finished; True means extraction succeeded."

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._download_url: str | None = None
        "Url of the update archive being downloaded, so that it can be cancelled."
        self._download_attempt: str | None = None
        "Identifies the current download so late callbacks cannot overwrite a retry."
        self._download_dir: Path | None = None
        "Temporary directory holding the downloaded archive."
        self._cancel_requested: bool = False
        self._install_thread: threading.Thread | None = None
        self._install_cancel: threading.Event = threading.Event()
        self._install_version: str | None = None

        self.update_info: UpdateInfo = UpdateInfo(UpdateStatus.none)
        "Every UI required info. Mutable."

        _ = self._install_event.connect(self._emit_update_info, Qt.ConnectionType.QueuedConnection)
        _ = self._install_finished.connect(
            self._on_install_finished, Qt.ConnectionType.QueuedConnection
        )

        self._network: NetworkClient = NetworkClient()
        self._apply_domain_override()
        try:
            cleanup_old_versions()
        except OSError as exc:
            logger.debug("Could not clean old versions: %s", exc)

    def _apply_domain_override(self) -> None:
        if (domains := args.update_domain) is not None:
            logger.debug("Fetching from custom domain: '%s'", domains[0])
            NetworkClient.set_base_url(GITHUB_SERVICE, domains[0])
            self.update_info.domain = domains[0]

    def get_latest_release(
        self, callback: Callable[[GithubLatestRelease | NetworkError], None]
    ) -> None:
        """Fetches the latest release from GitHub.

        Args:
            callback (Callable): Called with the release, or with a NetworkError if it could not be
                fetched.
        """
        logger.debug("Fetching github for latest release.")
        uri = NetworkClient.resolve(
            GITHUB_SERVICE,
            DEFAULT_GITHUB_DOMAIN,
            f"repos/{REPO_OWNER}/{REPO_NAME}/releases/latest",
        )

        def _on_fetched(result: bytes | NetworkError) -> None:
            if isinstance(result, NetworkError):
                logger.warning("Failed to fetch latest release from github: %s", result.error_str)
                callback(result)
                return
            try:
                callback(GithubLatestRelease.model_validate_json(result))
            except ValidationError as e:
                logger.warning("Unexpected release payload from github: %s", e)
                callback(NetworkError(f"Unexpected release payload from github: {e}", uri))

        self._network.fetch(uri, _on_fetched)

    def check_update(self) -> None:
        if self.update_info.state in {
            UpdateStatus.update_checking,
            UpdateStatus.download_started,
            UpdateStatus.downloading,
            UpdateStatus.downloaded,
            UpdateStatus.installation_started,
            UpdateStatus.installing,
            UpdateStatus.installed,
            UpdateStatus.restart_queue,
        }:
            return

        logger.debug("Checking for update...")
        self.update_info.error = None
        self.update_info.update_available = None
        self.update_info.latest_release = None
        self.update_info.download_progress = None
        self.update_info.install_progress = None
        self.update_info.state = UpdateStatus.update_checking
        self._emit_update_info()

        def _callback(release: GithubLatestRelease | NetworkError) -> None:
            if isinstance(release, NetworkError):
                self.update_info.state = UpdateStatus.none
                self.update_info.update_available = None
                self.update_info.latest_release = None
                self.update_info.error = release
                self._emit_update_info()
            elif release.get_version() > APPLICATION_VERSION:
                logger.debug("Update available: %s", release.tag_name)
                self.update_info.state = UpdateStatus.update_checked
                self.update_info.update_available = True
                self.update_info.latest_release = release
                self.update_info.error = None
                self._emit_update_info()
            else:
                logger.debug(f"{APPLICATION_NAME.title()} is upto date.")
                self.update_info.state = UpdateStatus.update_checked
                self.update_info.update_available = False
                self.update_info.latest_release = None
                self.update_info.error = None
                self._emit_update_info()

        self.get_latest_release(_callback)

    def download(self, release: GithubLatestRelease) -> bool:
        "Downloads the update archive of the given release."
        if self.update_info.state in {
            UpdateStatus.download_started,
            UpdateStatus.downloading,
            UpdateStatus.downloaded,
            UpdateStatus.installation_started,
            UpdateStatus.installing,
            UpdateStatus.installed,
            UpdateStatus.restart_queue,
        }:
            return False
        if self._install_thread is not None and self._install_thread.is_alive():
            return False

        if not _can_self_update():
            self.update_info.state = UpdateStatus.update_checked
            self.update_info.update_available = True
            self.update_info.latest_release = release
            self.update_info.error = Exception(
                "Automatic updates are only available in an installed build."
            )
            self._emit_update_info()
            return False

        self.update_info.error = None
        self.update_info.update_available = True
        self.update_info.latest_release = release
        self.update_info.install_progress = None
        self._cancel_requested = False

        # select the asset
        assets = _matching_assets(release.assets)
        if (x := len(assets)) != 1:
            logger.error(f"Aborting update due to {x} update assets found.")
            self.update_info.error = Exception(f"Update aborted due to {x} update assets found.")
            self.update_info.state = UpdateStatus.update_checked
            self._emit_update_info()
            return False
        file_asset = assets[0]
        file_name = Path(file_asset.name).name
        if file_name != file_asset.name:
            self.update_info.error = Exception("Update asset has an unsafe file name.")
            self.update_info.state = UpdateStatus.update_checked
            self._emit_update_info()
            return False

        tmp_dir = Path(tempfile.mkdtemp(prefix=f"{APPLICATION_NAME.title()}-update-"))
        file_path = tmp_dir / file_name
        url = file_asset.browser_download_url
        self._download_dir = tmp_dir
        attempt = uuid.uuid4().hex
        self._download_attempt = attempt

        self._download_url = url
        logger.debug("Update sequence started, downloading %s", url)
        self.update_info.state = UpdateStatus.download_started
        self.update_info.download_progress = None
        self._emit_update_info()

        def _on_downloaded(state: Downloaded) -> None:
            if self._download_attempt != attempt:
                return
            if state.aborted:
                self._download_url = None
                self._download_attempt = None
                self.update_info.download_progress = state
                if self._cancel_requested:
                    self._cancel_requested = False
                    self.update_info.state = UpdateStatus.download_aborted
                    self.update_info.error = None
                else:
                    self.update_info.state = UpdateStatus.update_checked
                    self.update_info.error = state.abort_reason or Exception("Download aborted.")
                    self._drop_download(immediate=True)
                self._emit_update_info()
                return

            self.update_info.download_progress = state
            if not state.completed:
                self.update_info.state = UpdateStatus.downloading
                self._emit_update_info()
                return

            self._download_url = None
            self._download_attempt = None
            self.update_info.state = UpdateStatus.downloaded
            self._emit_update_info()

            # Verify size.
            if not state.file_path.exists() or state.file_path.stat().st_size != file_asset.size:
                self._fail_update(
                    Exception("Download aborted due to size mismatch."),
                    state=UpdateStatus.update_checked,
                )
                return

            # Verify digest. GitHub reports it as "sha256:<hex>".
            if file_asset.digest:
                algorithm, _, expected = file_asset.digest.partition(":")
                if algorithm.casefold() not in {"", "sha256"}:
                    self._fail_update(
                        Exception(f"Unsupported digest algorithm: {algorithm}"),
                        state=UpdateStatus.update_checked,
                    )
                    return
                with open(state.file_path, "rb") as f:
                    digest = file_digest(f, "sha256").hexdigest()
                if digest.casefold() != expected.casefold():
                    self._fail_update(
                        Exception("Download aborted due to sha256 digest mismatch."),
                        state=UpdateStatus.update_checked,
                    )
                    return

            # Start extraction automatically. The UI can still cancel before activation.
            QTimer.singleShot(250, partial(self.install, state.file_path))

        self._network.download(url, file_path, _on_downloaded)
        return True

    def install(self, archive_path: Path) -> bool:
        """Extract a downloaded archive into a new version directory."""
        if self.update_info.state is not UpdateStatus.downloaded:
            return False
        if self._install_thread is not None and self._install_thread.is_alive():
            return False
        progress = self.update_info.download_progress
        if progress is None or progress.file_path != archive_path or not archive_path.is_file():
            self.update_info.error = Exception(
                "The downloaded update archive is no longer available."
            )
            self.update_info.state = UpdateStatus.update_checked
            self.update_info.download_progress = None
            self._emit_update_info()
            return False
        release = self.update_info.latest_release
        if release is None:
            self.update_info.error = Exception("No release information for installation.")
            self._emit_update_info()
            return False

        version = release.directory_version()
        self.update_info.error = None
        self.update_info.state = UpdateStatus.installation_started
        self.update_info.install_progress = InstallProgress(0, 0, False)
        self._install_version = version
        self._install_cancel.clear()
        self._emit_update_info()

        self._install_thread = threading.Thread(
            target=self._install_worker,
            args=(version, archive_path),
            name="ProsperoUpdateInstaller",
            daemon=True,
        )
        self._install_thread.start()
        return True

    def _install_worker(self, version: str, archive_path: Path) -> None:
        staging = versions_dir() / f".staging-{version}-{uuid.uuid4().hex}"
        try:
            total = self._extract_archive(archive_path, staging)
            if self._install_cancel.is_set():
                raise _InstallCancelled

            app_executable = staging / APPLICATION_NAME.title() / APP_EXECUTABLE_NAME
            if not app_executable.is_file():
                raise Exception(
                    f"Update archive did not contain {APPLICATION_NAME.title()}/{APP_EXECUTABLE_NAME}."
                )
            if os.name != "nt":
                os.chmod(app_executable, 0o755)

            final = version_dir(version)
            if final.exists():
                if current_version() == version:
                    raise Exception(f"Version {version} is already installed and current.")
                shutil.rmtree(final)
            os.replace(staging, final)

            self.update_info.install_progress = InstallProgress(total, total, True)
            self.update_info.state = UpdateStatus.installed
            self._install_event.emit()
            self._install_finished.emit(True)
        except _InstallCancelled:
            shutil.rmtree(staging, ignore_errors=True)
            self.update_info.state = UpdateStatus.downloaded
            self.update_info.install_progress = None
            self._install_event.emit()
            self._install_finished.emit(False)
        except Exception as exc:
            logger.exception("Update installation failed")
            shutil.rmtree(staging, ignore_errors=True)
            self.update_info.error = exc
            self.update_info.state = UpdateStatus.downloaded
            self.update_info.install_progress = None
            self._install_event.emit()
            self._install_finished.emit(False)

    def _extract_archive(self, archive_path: Path, destination: Path) -> int:
        if zipfile.is_zipfile(archive_path):
            return self._extract_zip(archive_path, destination)
        if tarfile.is_tarfile(archive_path):
            return self._extract_tar(archive_path, destination)
        raise Exception(f"Unsupported update archive: {archive_path.name}")

    def _extract_zip(self, archive_path: Path, destination: Path) -> int:
        with zipfile.ZipFile(archive_path) as archive:
            members: list[tuple[zipfile.ZipInfo, PurePosixPath]] = [
                (info, _safe_member(info.filename))
                for info in archive.infolist()
                if info.filename not in {"", ".", "./"}
            ]
            selected = _selected_members(members)
            files = [(info, path) for info, path in selected if not info.is_dir()]
            total = sum(info.file_size for info, _ in files)
            installed = 0
            for info, relative in selected:
                if self._install_cancel.is_set():
                    raise _InstallCancelled
                target = destination / relative
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, open(target, "wb") as output:
                    installed = self._copy_with_progress(source, output, total, installed)
                mode = (info.external_attr >> 16) & 0o777
                if mode:
                    try:
                        os.chmod(target, mode)
                    except OSError:
                        pass
            return total

    def _extract_tar(self, archive_path: Path, destination: Path) -> int:
        with tarfile.open(archive_path, mode="r:*") as archive:
            members: list[tuple[tarfile.TarInfo, PurePosixPath]] = []
            for member in archive.getmembers():
                if member.name in {"", ".", "./"}:
                    continue
                if member.islnk():
                    raise Exception(f"Hard links are not allowed in update archives: {member.name}")
                members.append((member, _safe_member(member.name)))
            selected = _selected_members(members)
            files = [(member, path) for member, path in selected if member.isfile()]
            total = sum(member.size for member, _ in files)
            installed = 0
            for member, relative in selected:
                if self._install_cancel.is_set():
                    raise _InstallCancelled
                target = destination / relative
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if member.issym():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    os.symlink(_safe_link_target(relative, member.linkname), target)
                    continue
                if not member.isfile():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise Exception(f"Could not read {member.name} from update archive.")
                with source, open(target, "wb") as output:
                    installed = self._copy_with_progress(source, output, total, installed)
                mode = member.mode & 0o777
                if mode:
                    try:
                        os.chmod(target, mode)
                    except OSError:
                        pass
            return total

    def _copy_with_progress(
        self,
        source: IO[bytes],
        output: IO[bytes],
        total: int,
        installed: int,
    ) -> int:
        while True:
            if self._install_cancel.is_set():
                raise _InstallCancelled
            chunk = source.read(_CHUNK_SIZE)
            if not chunk:
                break
            _ = output.write(chunk)
            installed += len(chunk)
            self.update_info.state = UpdateStatus.installing
            self.update_info.install_progress = InstallProgress(total, installed, False)
            self._install_event.emit()
        return installed

    def _on_install_finished(self, success: bool) -> None:
        self._install_thread = None
        if success and self._install_cancel.is_set():
            # The user cancelled while the worker was committing its last chunk.
            success = False
        if not success:
            cancelled = self._install_cancel.is_set()
            self._install_cancel.clear()
            self._drop_download(immediate=True)
            self.update_info.state = UpdateStatus.update_checked
            self.update_info.download_progress = None
            self.update_info.install_progress = None
            if not cancelled and self.update_info.error is None:
                self.update_info.error = Exception("Update installation failed.")
            self._emit_update_info()
            return

        version = self._install_version
        activated = False
        try:
            activated = version is not None and commit_install(version)
        except Exception:
            logger.exception("Could not activate the downloaded update")
        if not activated:
            self.update_info.state = UpdateStatus.downloaded
            self.update_info.install_progress = None
            self.update_info.error = Exception("Could not activate the downloaded update.")
            self._emit_update_info()
            return

        self.update_info.state = UpdateStatus.restart_queue
        self._emit_update_info()
        self._drop_download(immediate=True)
        QTimer.singleShot(400, self._restart)

    def _restart(self) -> None:
        restarted = False
        try:
            restarted = restart_app()
        except Exception:
            logger.exception("Could not restart the application after updating")
        if not restarted:
            self.update_info.state = UpdateStatus.installed
            self.update_info.error = Exception(
                "Update installed, but the application could not restart automatically."
            )
            self._emit_update_info()
            return
        logger.debug("Quitting application for the update to complete.")
        app = QApplication.instance()
        if app is None:
            logger.warning("Failed to quit the application unexpectedly.")
            return
        app.quit()

    def _fail_update(self, error: Exception, *, state: UpdateStatus) -> None:
        self._drop_download(immediate=True)
        self.update_info.state = state
        self.update_info.download_progress = None
        self.update_info.install_progress = None
        self.update_info.error = error
        self._emit_update_info()

    def _drop_download(self, *, immediate: bool) -> None:
        directory, self._download_dir = self._download_dir, None
        if directory is None:
            return
        if immediate:
            shutil.rmtree(directory, ignore_errors=True)
            return
        QTimer.singleShot(1000, partial(shutil.rmtree, directory, ignore_errors=True))

    def cancel_update(self) -> None:
        state = self.update_info.state
        if state in {UpdateStatus.download_started, UpdateStatus.downloading}:
            logger.debug("Update download aborted.")
            self._cancel_requested = True
            self._download_attempt = None
            url, self._download_url = self._download_url, None
            if url is not None:
                self._network.cancel(url)
            if (progress := self.update_info.download_progress) is not None:
                self.update_info.download_progress = replace(
                    progress,
                    aborted=True,
                    completed=False,
                    abort_reason=NetworkError("Download cancelled.", aborted=True),
                )
            self.update_info.state = UpdateStatus.download_aborted
            self.update_info.error = None
            self._drop_download(immediate=False)
            self._emit_update_info()
        elif state in {
            UpdateStatus.installation_started,
            UpdateStatus.installing,
        }:
            logger.debug("Update installation aborted.")
            self._install_cancel.set()
            self.update_info.state = UpdateStatus.downloaded
            self.update_info.install_progress = None
            self.update_info.error = None
            self._emit_update_info()
        elif state is UpdateStatus.downloaded:
            logger.debug("Downloaded update discarded.")
            self._drop_download(immediate=True)
            self.update_info.state = UpdateStatus.update_checked
            self.update_info.download_progress = None
            self.update_info.install_progress = None
            self.update_info.error = None
            self._emit_update_info()

    def restart(self) -> None:
        """Retry restarting after an update when automatic restart failed."""
        self.update_info.error = None
        self._restart()

    def _emit_update_info(self) -> None:
        self.update_info_updated.emit(self.update_info)
