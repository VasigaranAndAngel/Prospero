from typing import cast, override

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from constants import APPLICATION_NAME, VERSION
from data_objects import IconLoadMethod, LoadMethod
from helpers import SingletonQObjectMeta

# Narrow on NetworkError itself rather than Updater.GithubFetchError. They are the same
# class at runtime, but GithubFetchError is a class attribute, and a type checker cannot
# use an attribute to narrow an isinstance check.
from network import NetworkError
from shared_ui_elements import ResultBox
from updater import Downloaded, GithubLatestRelease, UpdateInfo, Updater, UpdateStatus

from ..base_result import BaseResult, ExecutionAction


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
        _ = self._updater.update_info_updated.connect(self._on_update_info)

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

    def _on_update_info(self, update_info: UpdateInfo) -> None:
        if (er := update_info.error) is not None:
            if isinstance(er, NetworkError):
                er_str = er.error_str
            else:
                er_str = str(er)
            self.set_description(
                f"{update_info.state.name.replace('_', ' ').title()} Error: {er_str}"
            )
            return

        match update_info.state:
            case UpdateStatus.none:
                pass
            case UpdateStatus.update_checking:
                pass
            case UpdateStatus.update_checked:
                self._on_update_checked(update_info.latest_release)
            case UpdateStatus.download_aborted:
                self._on_update_aborted()
            case UpdateStatus.download_started:
                self._on_download_started()
            case UpdateStatus.downloading | UpdateStatus.downloaded:
                if update_info.download_progress is not None:
                    self._update_download_state(update_info.download_progress)
            case _:  # TODO: handle other status
                pass

    def _update_download_state(self, download_state: Downloaded) -> None:
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

    def _on_update_aborted(self) -> None:
        self._update_progress_bar(0.0)
        self._icon.update_load_method(IconLoadMethod(LoadMethod.default))
        self.set_description("Update aborted")
        QTimer.singleShot(1500, self._update_name_and_description)

    def _on_update_checked(self, release: GithubLatestRelease | NetworkError | None) -> None:
        if isinstance(release, NetworkError):
            desc = release.error_str
        elif release is None:
            desc = "No updates available."
        else:
            desc = f"Version {release.tag_name} available."

        self.set_description(desc)
        QTimer.singleShot(len(desc) * 80, self._update_name_and_description)

    def _update_name_and_description(self) -> None:
        if (er := self._updater.update_info.error) is not None:
            if isinstance(er, NetworkError):
                er_str = er.error_str
            else:
                er_str = str(er)
            self.set_description(
                f"{self._updater.update_info.state.name.replace('_', ' ').title()} Error: {er_str}"
            )
            return
        if self._updater.update_info.latest_release is None:
            self.set_name("Check for update")
            self.set_description(f"Checks if new version of {APPLICATION_NAME.title()} available.")
        else:
            self.set_name(f"Update {APPLICATION_NAME.title()}")
            self.set_description(
                f"Update {APPLICATION_NAME.title()} from {VERSION} to {self._updater.update_info.latest_release.tag_name}."
            )

    def _update_progress_bar(self, value: float) -> None:
        self._progress_anim.stop()
        self._progress_anim.setEndValue(value)
        self._progress_anim.start()
        self._progress2_anim.stop()
        self._progress2_anim.setEndValue(value)
        self._progress2_anim.start()

    def _check_for_update(self) -> None:
        if self._updater.update_info.state is UpdateStatus.none:
            self.set_description("Checking for updates...")
            self._updater.check_update()

    @override
    def request_deletion(self) -> None:
        self.hide()

    @override
    def update_result(self, new_result: "BaseResult") -> None:
        super().update_result(new_result)
        self._update_name_and_description()

    @override
    def execute_execution_action(self, action: ExecutionAction) -> None:
        if action is ExecutionAction.Trigger:
            if self._updater.update_info.state is UpdateStatus.none:
                self._check_for_update()
            else:
                if self._updater.update_info.state in {
                    UpdateStatus.download_started,
                    UpdateStatus.downloading,
                }:
                    self._updater.cancel_update()
                elif self._updater.update_info.latest_release is not None:
                    self.set_description("Preparing to update...")
                    _ = self._updater.download(self._updater.update_info.latest_release)
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
