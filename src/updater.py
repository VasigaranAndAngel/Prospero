import logging
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
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
from platform_specific.updater import run_installer

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


class Updater(QObject, metaclass=SingletonQObjectMeta):
    """This is a singleton object which can check for new version of application and download and
    install it. Since it is inherited QObject this class should be initialized after a QApplication
    instance is created.

    Networking is delegated to :class:`network.NetworkClient`, so this class only knows how to speak
    the GitHub release API and how to launch the installer.
    """

    GithubFetchError: type[NetworkError] = NetworkError
    "Kept for callers that test for it by name. NetworkError is the type itself."

    update_checked: Signal = Signal(object)
    """Emitted with a GithubLatestRelease of latest version if available else emitted with None.
    In case of error, a NetworkError is emitted.
    """
    downloaded: Signal = Signal(Downloaded)
    "Will be emitted while the file is downloading and downloaded."
    download_started: Signal = Signal()
    "Will be emitted when downloading started."

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._update_progress: bool = False
        self._download_url: str | None = None
        "Url of the installer being downloaded, so that it can be cancelled."

        self._network: NetworkClient = NetworkClient()
        self._apply_domain_override()

    def _apply_domain_override(self) -> None:
        if (domains := args.update_domain) is not None:
            logger.debug("Fetching from custom domain: '%s'", domains[0])
            NetworkClient.set_base_url(GITHUB_SERVICE, domains[0])

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

        def _callback(release: GithubLatestRelease | NetworkError) -> None:
            if isinstance(release, NetworkError):
                self.update_checked.emit(release)
            elif release.get_version() > APPLICATION_VERSION:
                logger.debug("Update available: %s", release.tag_name)
                self.update_checked.emit(release)
            else:
                logger.debug(f"{APPLICATION_NAME.title()} is upto date.")
                self.update_checked.emit(None)

        self.get_latest_release(_callback)

    def update(self, release: GithubLatestRelease) -> None:
        """Downloads Prosper of version of given release and update the application.

        Emits the self.downloaded with Downloaded parameter to update the progress of download.

        Args:
            release (GithubLatestRelease): github release to download the file from.
        """
        if self._update_progress:
            return

        file_asset = release.assets[0]
        tmp_dir = tempfile.mkdtemp(prefix=APPLICATION_NAME.title() + " Installer")
        file_path = Path(tmp_dir) / file_asset.name
        url = file_asset.browser_download_url

        self._update_progress = True
        self._download_url = url
        logger.debug("Update sequence started, downloading %s", url)
        self.download_started.emit()

        def _on_downloaded(state: Downloaded) -> None:
            self._update_progress = not (state.completed or state.aborted)
            self._download_url = None
            self.downloaded.emit(state)
            if state.completed:
                QTimer.singleShot(1000, lambda: self._run_installer(state.file_path))

        self._network.download(url, file_path, _on_downloaded)

    def cancel_update(self) -> None:
        if not self._update_progress:
            return

        logger.debug("Update aborted.")
        self._update_progress = False
        url, self._download_url = self._download_url, None

        if url is None:
            self.downloaded.emit(Downloaded(0, 0, 0, False, Path(), aborted=True))
        else:
            # The client reports the aborted transfer, so no state is emitted here.
            self._network.cancel(url)

    def _run_installer(self, installer_path: Path) -> None:
        if not run_installer(installer_path):
            logger.warning(
                "Automatic update installation is not implemented on this platform; "
                + "downloaded %s but will not run it.",
                installer_path,
            )
            return

        logger.debug("Quitting application for the update to complete.")
        ins = QApplication.instance()
        if ins is None:
            logger.warning("Failed to quit the application unexpectedly.")
            return
        ins.quit()
