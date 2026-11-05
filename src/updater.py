import fnmatch
import logging
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from hashlib import file_digest
from pathlib import Path
from typing import ClassVar, Final, Literal

from packaging.version import Version
from pydantic import BaseModel, ConfigDict, ValidationError
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QWidget

from arg_parser import args
from constants import APPLICATION_NAME, APPLICATION_VERSION, REPO_NAME, REPO_OWNER
from helpers import SingletonQObjectMeta
from network import Downloaded, NetworkClient, NetworkError
from platform_specific.updater import FILE_MATCH_PAT, run_installer

logger = logging.getLogger(__name__)

GITHUB_SERVICE: Final[str] = "github"
"Service name used to register a base url override for the GitHub API."

DEFAULT_GITHUB_DOMAIN: Final[str] = "https://api.github.com"

__all__ = ["Downloaded", "GithubLatestRelease", "NetworkError", "Updater"]


@dataclass
class _GithubAsset(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    browser_download_url: str
    name: str
    label: str | None
    state: Literal["uploaded", "open"]
    content_type: str
    size: int
    digest: str | None


class GithubLatestRelease(BaseModel):
    "A model to validate latest release from github"

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    tag_name: str
    name: str
    body: str | None
    assets: list[_GithubAsset]

    def get_version(self) -> Version:
        return Version(self.tag_name)


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
class UpdateProgress:
    total: float
    completed: float

    @property
    def ratio(self) -> float:
        return self.completed / self.total


@dataclass
class UpdateInfo:
    "Single object which contains all UI needed info and will be used over an entire update process."

    state: UpdateStatus
    update_available: bool | None = None
    latest_release: GithubLatestRelease | None = None
    download_progress: Downloaded | None = None
    install_progress: UpdateProgress | None = None
    error: Exception | NetworkError | None = None
    domain: str | None = None


class Updater(QObject, metaclass=SingletonQObjectMeta):
    """This is a singleton object which can check for new version of application and download and
    install it. Since it is inherited QObject this class should be initialized after a QApplication
    instance is created.

    Networking is delegated to :class:`network.NetworkClient`, so this class only knows how to speak
    the GitHub release API and how to launch the installer.
    """

    GithubFetchError: type[NetworkError] = NetworkError
    "Kept for callers that test for it by name. NetworkError is the type itself."

    update_info_updated: Signal = Signal(UpdateInfo)
    """Emitted with UpdateInfo with the current state of update process."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._update_progress: bool = False
        self._download_url: str | None = None
        "Url of the installer being downloaded, so that it can be cancelled."
        self.update_info: UpdateInfo = UpdateInfo(UpdateStatus.none)
        "Every UI required info. Mutable."

        self._network: NetworkClient = NetworkClient()
        self._apply_domain_override()

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
        logger.debug("Checking for update...")
        self.update_info.state = UpdateStatus.update_checking
        self._emit_update_info()

        def _callback(release: GithubLatestRelease | NetworkError) -> None:
            if isinstance(release, NetworkError):
                self.update_info.error = release
                self._emit_update_info()
                self.update_info.error = None
            elif release.get_version() > APPLICATION_VERSION:
                logger.debug("Update available: %s", release.tag_name)
                self.update_info.state = UpdateStatus.update_checked
                self.update_info.update_available = True
                self.update_info.latest_release = release
                self._emit_update_info()
            else:
                logger.debug(f"{APPLICATION_NAME.title()} is upto date.")
                self.update_info.state = UpdateStatus.update_checked
                self.update_info.update_available = False
                self._emit_update_info()

        self.get_latest_release(_callback)

    def download(self, release: GithubLatestRelease) -> bool:
        "Downloads Prospero of version of given release."
        if self.update_info.state in {
            UpdateStatus.download_started,
            UpdateStatus.downloading,
            UpdateStatus.downloaded,
        }:
            return False

        # select the asset
        assets = tuple(filter(lambda x: fnmatch.fnmatch(x.name, FILE_MATCH_PAT), release.assets))
        if (x := len(assets)) != 1:
            logger.error(f"Aborting update due to {x} update assets found.")
            self.update_info.error = Exception(f"Update aborted due to {x} update assets found.")
            self._emit_update_info()
            self.update_info.error = None
            return False
        file_asset = assets[0]

        tmp_dir = tempfile.mkdtemp(prefix=APPLICATION_NAME.title() + " Installer")
        file_path = Path(tmp_dir) / file_asset.name
        url = file_asset.browser_download_url

        self._update_progress = True
        self._download_url = url
        logger.debug("Update sequence started, downloading %s", url)
        self.update_info.state = UpdateStatus.download_started
        self._emit_update_info()

        def _on_downloaded(state: Downloaded) -> None:
            if state.aborted or state.completed:
                self._update_progress = False
                self._download_url = None
                if state.aborted:
                    self.update_info.state = UpdateStatus.download_aborted
                else:
                    self.update_info.state = UpdateStatus.downloaded
            else:
                self.update_info.state = UpdateStatus.downloading
            self.update_info.download_progress = state
            self._emit_update_info()

            if state.completed:  # TODO: check if auto install allowed in config
                # verify size
                if (
                    not state.file_path.exists()
                    or state.file_path.stat().st_size != file_asset.size
                ):
                    self._cleanup_download()
                    self.update_info.error = Exception("Download aborted due to size missmatch.")
                    self._emit_update_info()
                    self.update_info.error = None

                # verify digest
                if file_asset.digest is not None:
                    with open(state.file_path, "rb") as f:
                        digest = file_digest(f, "sha256").hexdigest()
                    if digest.casefold() != file_asset.digest.casefold().removeprefix("sha256:"):
                        self._cleanup_download()
                        self.update_info.error = Exception(
                            "Download aborted due to sha256 digest missmatch."
                        )
                        self._emit_update_info()
                        self.update_info.error = None

                # start installer (installation should be started by the UI)
                # TODO: start installation only if auto install enabled in configs
                # QTimer.singleShot(1000, lambda: self.install(state.file_path))

        self._network.download(url, file_path, _on_downloaded)
        return True

    def _cleanup_download(self) -> None:
        down_progress = self.update_info.download_progress
        if down_progress is None:
            return
        file_path = down_progress.file_path
        if file_path.exists():
            file_path.unlink()

    def cancel_update(self) -> None:
        if not self._update_progress:
            return

        logger.debug("Update aborted.")
        self._update_progress = False
        url, self._download_url = self._download_url, None

        if url is not None:
            self._network.cancel(url)
        QTimer.singleShot(1000, self._cleanup_download)
        self.update_info.state = UpdateStatus.download_aborted
        self._emit_update_info()

    def install(self, file_path: Path) -> None:
        # TODO: Update files to new dir and give update progress info to UI
        if not run_installer(file_path):
            return

        logger.debug("Quitting application for the update to complete.")
        ins = QApplication.instance()
        if ins is None:
            logger.warning("Failed to quit the application unexpectedly.")
            return
        ins.quit()

    def _emit_update_info(self) -> None:
        self.update_info_updated.emit(self.update_info)
