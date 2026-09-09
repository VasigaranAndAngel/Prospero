import logging
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import ClassVar, Literal

from packaging.version import Version
from pydantic import BaseModel, ConfigDict
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QApplication, QWidget

from constants import APPLICATION_NAME, APPLICATION_VERSION, REPO_NAME, REPO_OWNER
from helpers import SingletonQObjectMeta

logger = logging.getLogger(__name__)


@dataclass
class Downloaded:
    download_progress: float
    downloaded_size: int
    total_size: int
    completed: bool
    file_path: Path
    speed: float | None = None
    aborted: bool = False


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
    """

    @dataclass(frozen=True)
    class GithubFetchError:
        error_str: str = "Failed to fetch from github."

    update_checked: Signal = Signal(object)
    """Emitted with a GithubLatestRelease of latest version if available else emitted with None.
    In case of error, Updater.GithubFetchError is emitted.
    """
    downloaded: Signal = Signal(Downloaded)
    "Will be emitted while the file is downloading and downloaded."
    download_started: Signal = Signal()
    "Will be emitted when downloading started."

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._update_progress: bool = False
        self._downloading: QNetworkReply | None = None
        self._network_manager: QNetworkAccessManager = QNetworkAccessManager()

    def _prepare_release_and_send(
        self,
        reply: QNetworkReply,
        sent_to: Callable[[GithubLatestRelease | GithubFetchError], None],
    ) -> None:
        if reply.error() == QNetworkReply.NetworkError.NoError:
            try:
                data = reply.readAll().data()
                if isinstance(data, memoryview):
                    logger.warning(
                        f"Failed to fetch ({reply.url().toString()}) latest release from github: data type is {memoryview}"
                    )
                    sent_to(self.GithubFetchError())
                    return

                release = GithubLatestRelease.model_validate_json(data)
                sent_to(release)
            except Exception as e:
                logger.warning(f"Failed to fetch ({reply.url().toString()}) latest release from github: {e}")
                sent_to(self.GithubFetchError())
        else:
            logger.warning(f"Failed to fetch ({reply.url().toString()}) latest release from github: {reply.errorString()}")
            sent_to(self.GithubFetchError())

    def get_latest_release(
        self, callback: Callable[[GithubLatestRelease | GithubFetchError], None]
    ) -> None:
        logger.debug("Fetching github for latest release.")
        if (
            "update-domain" in sys.argv
            and len(sys.argv) > (x := sys.argv.index("update-domain")) + 1
        ):
            domain = sys.argv[x + 1]
            logger.debug(f"Fetching from custom domain: '{domain}'")
        else:
            domain = "https://api.github.com"
        uri = f"{domain}/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
        reply = self._network_manager.get(QNetworkRequest(uri))

        _ = reply.finished.connect(partial(self._prepare_release_and_send, reply, callback))

    def check_update(self) -> None:
        logger.debug("Checking for update...")

        def _callback(release: "GithubLatestRelease | Updater.GithubFetchError") -> None:
            if isinstance(release, Updater.GithubFetchError):
                self.update_checked.emit(release)
            elif (
                isinstance(release, Updater.GithubFetchError)
                or release.get_version() > APPLICATION_VERSION
            ):
                logger.debug(f"Update available: {release.tag_name}")
                self.update_checked.emit(release)
            else:
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
        self._update_progress = True
        logger.debug("Update sequence started...")
        file_asset = release.assets[0]
        tmp_dir = tempfile.mkdtemp(prefix=APPLICATION_NAME.title() + " Installer")
        file_path = Path(tmp_dir) / file_asset.name

        reply = self._network_manager.get(QNetworkRequest(file_asset.browser_download_url))
        self.download_started.emit()
        self._downloading = reply
        started_at = time.time()

        def _on_downloading(downloaded: int, total: int) -> None:
            ct = time.time()
            speed = downloaded / (ct - started_at)  # average speed
            self.downloaded.emit(
                Downloaded(downloaded / total, downloaded, total, False, file_path, speed)
            )

        def _on_downloaded() -> None:
            if self._update_progress:
                _ = file_path.write_bytes(reply.readAll().data())
                self.downloaded.emit(
                    Downloaded(1, file_asset.size, file_asset.size, True, file_path)
                )
                self._downloading = None
                QTimer.singleShot(1000, lambda: self._run_installer(file_path))

        _ = reply.downloadProgress.connect(_on_downloading)
        _ = reply.finished.connect(_on_downloaded)

    def cancel_update(self) -> None:
        if self._downloading is not None:
            self._update_progress = False
            self._downloading.abort()
            self._downloading = None
            logger.debug("Update aborted.")
            self.downloaded.emit(Downloaded(0, 0, 0, False, Path(), aborted=True))

    def _run_installer(self, installer_path: Path) -> None:
        cmd = [str(installer_path)]

        if getattr(sys, "frozen", False):
            install_dir = getattr(sys, "_MEIPASS")  # pyright: ignore[reportAny]
            if install_dir is None:
                logger.warning("Not able to get the install dir.")
            else:
                cmd.append("/silent")
                cmd.append("/autostart")
                cmd.append(f"/dir={install_dir}")
        else:
            cmd.append("/silent")
            cmd.append("/autostart")
            cmd.append(f"/dir={Path('./install_dir').resolve()}")

        logger.debug(f"Starting installer: {cmd=}")
        _ = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        logger.debug("Quitting application for the update to complete.")
        ins = QApplication.instance()
        if ins is None:
            logger.warning("Failed to quit the application unexpectedly.")
            return
        ins.quit()
