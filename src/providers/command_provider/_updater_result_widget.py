from typing import cast, override

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from constants import APPLICATION_NAME, VERSION
from data_objects import IconLoadMethod, LoadMethod
from helpers import SingletonQObjectMeta
from updater import Downloaded, GithubLatestRelease, Updater

from ..base_result_and_widgets import BaseResult, ExecutionAction, ResultBox


def readable_size(num: float):
    for unit in ("B", "KiB", "MiB"):
        if num < 1024.0:
            return f"{num:3.1f}{unit}"
        num /= 1024.0
    return f"{num:.1f}GiB"


class UpdaterResultWidget(ResultBox, metaclass=SingletonQObjectMeta):
    def __init__(self, text: str, result: BaseResult, /, parent: QWidget | None = None) -> None:
        super().__init__(text, result, parent)

        self._updater: Updater = Updater()
        _ = self._updater.downloaded.connect(self._update_download_state)
        _ = self._updater.download_started.connect(self._on_download_started)
        _ = self._updater.update_checked.connect(self._on_update_checked)

        self._update_checking: bool = False
        self._update_progress: bool = False
        self._latest_release: GithubLatestRelease | None = None

        self._update_name_and_description()

        _ = self.setProperty("_progress", 0.0)
        self._progress_anim: QPropertyAnimation = QPropertyAnimation(self, b"_progress", self)
        self._progress_anim.setDuration(500)
        self._progress_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        _ = self._progress_anim.valueChanged.connect(self.repaint)

        _ = self.setProperty("_progress2", 0.0)
        self._progress2_anim: QPropertyAnimation = QPropertyAnimation(self, b"_progress2", self)
        self._progress2_anim.setDuration(500)
        self._progress2_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        _ = self._progress2_anim.finished.connect(self.repaint)  # progress_anim repaints each frame

    def _update_download_state(self, download_state: Downloaded) -> None:
        if download_state.aborted:
            return self._on_update_aborted()
        x = "Downloaded" if download_state.completed else "Downloading"
        f = download_state.file_path.name
        d = readable_size(download_state.downloaded_size)
        t = readable_size(download_state.total_size)
        p = f"{download_state.download_progress * 100:.2f}%"
        s = f"{readable_size(download_state.speed)}/s" if download_state.speed is not None else ""
        # Downloading ProsperoSetup-0.0.1.exe    15MiB/40MiB (20.0%)    5MiB/s
        desc = f"{x} {f}    {d}/{t} ({p})    {s}"
        self.set_description(desc)
        self._update_progress_bar(download_state.download_progress)

    def _on_download_started(self) -> None:
        self._icon.update_load_method(IconLoadMethod(LoadMethod.loading))
        self._update_progress = True

    def _on_update_aborted(self) -> None:
        self._update_progress_bar(0.0)
        self._icon.update_load_method(IconLoadMethod(LoadMethod.default))
        self._update_progress = False
        self.set_description("Update aborted")
        QTimer.singleShot(1500, self._update_name_and_description)

    def _on_update_checked(
        self, release: GithubLatestRelease | Updater.GithubFetchError | None
    ) -> None:
        self._update_checking = False
        self._latest_release = None

        if isinstance(release, Updater.GithubFetchError):
            desc = release.error_str
        elif release is None:
            desc = "No updates available."
        else:
            self._latest_release = release
            desc = f"Version {release.tag_name} available."

        self.set_description(desc)
        QTimer.singleShot(len(desc) * 80, self._update_name_and_description)

    def _update_name_and_description(self) -> None:
        if self._latest_release is None:
            self.set_name(f"Check for update")
            self.set_description(f"Checks if new version of {APPLICATION_NAME.title()} available.")
        else:
            self.set_name(f"Update {APPLICATION_NAME.title()}")
            self.set_description(
                f"Update {APPLICATION_NAME.title()} from {VERSION} to {self._latest_release.tag_name}."
            )

    def _update_progress_bar(self, value: float) -> None:
        self._progress_anim.stop()
        self._progress_anim.setEndValue(value)
        self._progress_anim.start()
        self._progress2_anim.stop()
        self._progress2_anim.setEndValue(value)
        self._progress2_anim.start()

    def _check_for_update(self) -> None:
        if not self._update_checking:
            self._update_checking = True
            self.set_description("Checking for updates...")
            self._updater.check_update()

    @classmethod
    def set_latest_release(cls, release: GithubLatestRelease) -> None:
        cls._latest_release = release

    @override
    def request_deletion(self) -> None:
        self.hide()

    @override
    def execute_execution_action(self, action: ExecutionAction) -> None:
        if action in ExecutionAction.Trigger:
            if self._latest_release is None:
                self._check_for_update()
            else:
                if self._update_progress:
                    self._updater.cancel_update()
                else:
                    self.set_description("Preparing to update...")
                    self._updater.update(self._latest_release)
        else:
            return super().execute_execution_action(action)

    @override
    def paintEvent(self, event: QPaintEvent, /) -> None:
        width = cast(float, self.property("_progress")) * self.width()
        width2 = cast(float, self.property("_progress2")) * self.width()
        if max(width, width2) > 0:
            with QPainter(self) as p:
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor(255, 0, 0, 50)))
                p.drawRect(self.rect().toRectF().adjusted(0, 0, width - self.width(), 0))
                if width != width2:
                    gr_rect = self.rect().toRectF().adjusted(width2, 0, width - self.width(), 0)
                    gr = QLinearGradient(gr_rect.topLeft(), gr_rect.topRight())
                    gr.setColorAt(0, QColor(255, 0, 0, 0))
                    gr.setColorAt(1, QColor(255, 0, 0, 50))
                    p.setBrush(gr)
                    p.drawRect(gr_rect)
        return super().paintEvent(event)
