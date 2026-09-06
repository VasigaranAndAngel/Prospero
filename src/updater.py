import logging
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from packaging.version import Version
from pydantic import BaseModel, ConfigDict
from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QApplication, QWidget

from constants import APPLICATION_NAME, APPLICATION_VERSION, REPO_NAME, REPO_OWNER

logger = logging.getLogger(__name__)


@dataclass
class Downloaded:
    downloaded_percent: float
    downloaded_size: int
    total_size: int
    completed: bool
    file_path: Path | None = None


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


class Updater(QObject):
    update_available: Signal = Signal(object)
    "Will be emitted with a GithubLatestRelease instance of latest version if available."

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._network_manager: QNetworkAccessManager = QNetworkAccessManager()

    def _prepare_release_and_send(
        self, reply: QNetworkReply, sent_to: Callable[[GithubLatestRelease], None]
    ) -> None:
        if reply.error() == QNetworkReply.NetworkError.NoError:
            try:
                data = reply.readAll().data()
                if isinstance(data, memoryview):
                    logger.warning(
                        f"Failed to fetch latest release from github: data type is {memoryview}"
                    )
                    return

                release = GithubLatestRelease.model_validate_json(data)
                sent_to(release)
            except Exception as e:
                logger.warning(f"Failed to fetch latest release from github: {e}")
        else:
            logger.warning(f"Failed to fetch latest release from github: {reply.errorString()}")

    def get_latest_release(self, callback: Callable[[GithubLatestRelease], None]) -> None:
        uri = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
        reply = self._network_manager.get(QNetworkRequest(uri))

        def _wrapper() -> None:
            self._prepare_release_and_send(reply, callback)

        _ = reply.finished.connect(_wrapper)

    def check_update(self) -> None:
        def _callback(release: GithubLatestRelease) -> None:
            if release.get_version() > APPLICATION_VERSION:
                self.update_available.emit()

        self.get_latest_release(_callback)

    def update(self, release: GithubLatestRelease, callback: Callable[[Downloaded], None]) -> None:
        """Downloads Prosper of version of given release and update the application.

        Calls callback with Downloaded parameter to update the progress of download.

        Args:
            release (GithubLatestRelease): github release to download the file from.
            callback (Callable[[Download], None]): A callable to call with download progress.
        """
        file_asset = release.assets[0]
        tmp_dir = tempfile.mkdtemp(prefix=APPLICATION_NAME.title() + " Installer")
        file_path = Path(tmp_dir) / file_asset.name

        # region download file
        reply = self._network_manager.get(QNetworkRequest(file_asset.browser_download_url))

        def _on_downloading(downloaded: int, total: int) -> None:
            callback(Downloaded(total / downloaded * 100, downloaded, total, False))

        def _on_downloaded() -> None:
            _ = file_path.write_bytes(reply.readAll().data())
            callback(Downloaded(100, file_asset.size, file_asset.size, True, file_path))

        _ = reply.downloadProgress.connect(_on_downloading)
        _ = reply.finished.connect(_on_downloaded)
        # endregion

        # region update application
        cmd = [str(file_path)]

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
        _ = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
        logger.debug("Quitting application for the update to complete.")
        ins = QApplication.instance()
        if ins is None:
            logger.warning("Failed to quit the application unexpectedly.")
            return
        ins.quit()
        # endregion
