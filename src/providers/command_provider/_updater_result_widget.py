from typing import cast, override

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from constants import APPLICATION_NAME, VERSION
from data_objects import IconLoadMethod, LoadMethod
from helpers import SingletonQObjectMeta
from network import NetworkError
from shared_ui_elements import ResultBox
from updater import Downloaded, UpdateInfo, Updater, UpdateStatus

from ..base_result import BaseResult, ExecutionAction


def readable_size(num: float) -> str:
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

        # Keep the update offer visible for a while, then fall back to the generic command.
        self._checked_update_timeout: QTimer = QTimer(
            self,
            singleShot=True,
            interval=1000 * 60 * 30,  # 30 minutes
        )
        _ = self._checked_update_timeout.timeout.connect(self._on_checked_update_timeout)

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
        _ = self._progress2_anim.finished.connect(self.repaint)

    def _on_update_info(self, _update_info: UpdateInfo) -> None:
        self._update_name_and_description()

    @staticmethod
    def _error_text(error: Exception | NetworkError | str) -> str:
        if isinstance(error, NetworkError):
            return error.error_str
        return str(error)

    def _update_name_and_description(self) -> None:
        ui = self._updater.update_info
        self._checked_update_timeout.stop()

        name = "Check for update"
        desc = f"Checks if a new version of {APPLICATION_NAME.title()} is available."
        icon = IconLoadMethod(LoadMethod.default)
        progress = 0.0

        if ui.error is not None:
            name = self._action_name(ui.state)
            desc = f"{name} failed: {self._error_text(ui.error)}"
        else:
            match ui.state:
                case UpdateStatus.none:
                    pass
                case UpdateStatus.update_checking:
                    name = "Check for update"
                    desc = f"Checking if a new version of {APPLICATION_NAME.title()} is available..."
                    icon = IconLoadMethod(LoadMethod.loading)
                case UpdateStatus.update_checked:
                    match ui.update_available:
                        case False:
                            name = "Check for update"
                            desc = (
                                f"No new version available. "
                                f"{APPLICATION_NAME.title()} {VERSION} is up to date."
                            )
                        case True:
                            name = f"Update {APPLICATION_NAME.title()}"
                            if ui.latest_release is None:
                                desc = f"New version of {APPLICATION_NAME.title()} available."
                            else:
                                desc = (
                                    f"Update {APPLICATION_NAME.title()} from {VERSION} to "
                                    f"{ui.latest_release.tag_name}. Press Enter to install."
                                )
                        case None:
                            desc = "Press Enter to check for updates."
                    self._checked_update_timeout.start()
                case UpdateStatus.download_started:
                    name = "Updating"
                    icon = IconLoadMethod(LoadMethod.loading)
                    desc = "Preparing download..."
                case UpdateStatus.downloading:
                    name = "Updating"
                    icon = IconLoadMethod(LoadMethod.loading)
                    if (dp := ui.download_progress) is not None:
                        desc = self._build_download_state(dp) + "    Press Enter to cancel."
                        progress = dp.download_progress
                    else:
                        desc = "Downloading... Press Enter to cancel."
                case UpdateStatus.downloaded:
                    name = "Updating"
                    desc = "Download complete. Preparing to install..."
                    progress = 1.0
                case UpdateStatus.download_aborted:
                    name = f"Update {APPLICATION_NAME.title()}"
                    desc = "Download aborted. Press Enter to try again."
                    progress = 0.0
                case UpdateStatus.installation_started:
                    name = "Updating"
                    desc = "Preparing to install..."
                    icon = IconLoadMethod(LoadMethod.loading)
                case UpdateStatus.installing:
                    name = "Updating"
                    icon = IconLoadMethod(LoadMethod.loading)
                    if (ip := ui.install_progress) is not None:
                        desc = f"Installing {ip.ratio * 100:.1f}%. Press Enter to cancel."
                        progress = ip.ratio
                    else:
                        desc = "Installing... Press Enter to cancel."
                case UpdateStatus.installed:
                    name = f"Restart {APPLICATION_NAME.title()}"
                    desc = "Update installed. Restarting..."
                    progress = 1.0
                case UpdateStatus.installation_queue:
                    name = "Updating"
                    desc = "Waiting to install..."
                case UpdateStatus.restart_queue:
                    name = f"Restart {APPLICATION_NAME.title()}"
                    desc = "Update installed. Restarting..."
                    progress = 1.0

        self.set_name(name)
        self.set_description(desc)
        self._icon.update_load_method(icon)
        self._update_progress_bar(progress)

    @staticmethod
    def _action_name(state: UpdateStatus) -> str:
        match state:
            case UpdateStatus.update_checked | UpdateStatus.download_aborted:
                return f"Update {APPLICATION_NAME.title()}"
            case UpdateStatus.downloaded:
                return f"Install {APPLICATION_NAME.title()}"
            case UpdateStatus.installed | UpdateStatus.restart_queue:
                return f"Restart {APPLICATION_NAME.title()}"
            case _:
                return "Check for update"

    @staticmethod
    def _build_download_state(download_state: Downloaded) -> str:
        state = "Downloaded" if download_state.completed else "Downloading"
        name = download_state.file_path.name
        downloaded = readable_size(download_state.downloaded_size)
        total = readable_size(download_state.total_size)
        percent = f"{download_state.download_progress * 100:.1f}%"
        speed = (
            f"{readable_size(download_state.speed)}/s"
            if download_state.speed is not None
            else ""
        )
        return f"{state} {name}    {downloaded}/{total} ({percent})    {speed}".rstrip()

    def _update_progress_bar(self, value: float) -> None:
        value = max(0.0, min(value, 1.0))
        self._progress_anim.stop()
        self._progress_anim.setEndValue(value)
        self._progress_anim.start()
        self._progress2_anim.stop()
        self._progress2_anim.setEndValue(value)
        self._progress2_anim.start()

    def _check_for_update(self) -> None:
        self.set_description("Checking for updates...")
        self._updater.check_update()

    def _on_checked_update_timeout(self) -> None:
        if self._updater.update_info.state is UpdateStatus.update_checked:
            self._updater.update_info.state = UpdateStatus.none
            self._updater.update_info.update_available = None
            self._updater.update_info.latest_release = None
            self._update_name_and_description()

    @override
    def request_deletion(self) -> None:
        self.hide()

    @override
    def update_result(self, new_result: "BaseResult") -> None:
        self.result = new_result  # pyright: ignore[reportUnannotatedClassAttribute]
        self._update_name_and_description()

    @override
    def execute_execution_action(self, action: ExecutionAction) -> None:
        if action is not ExecutionAction.Trigger:
            return super().execute_execution_action(action)

        ui = self._updater.update_info
        match ui.state:
            case UpdateStatus.none:
                self._check_for_update()
            case UpdateStatus.installed:
                self._updater.restart()
            case UpdateStatus.update_checking | UpdateStatus.restart_queue | UpdateStatus.installation_queue:
                # Nothing useful to do; the operation is in flight or about to restart.
                pass
            case (
                UpdateStatus.download_started
                | UpdateStatus.downloading
                | UpdateStatus.installation_started
                | UpdateStatus.installing
            ):
                self._updater.cancel_update()
            case UpdateStatus.update_checked | UpdateStatus.download_aborted:
                if ui.update_available is False:
                    self._check_for_update()
                elif ui.latest_release is not None:
                    self.set_description("Preparing to update...")
                    _ = self._updater.download(ui.latest_release)
                else:
                    self._check_for_update()
            case UpdateStatus.downloaded:
                dp = ui.download_progress
                if dp is not None and dp.file_path.is_file():
                    _ = self._updater.install(dp.file_path)
                else:
                    self._check_for_update()

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
