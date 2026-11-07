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
from updater import (
    Downloaded,
    UpdateInfo,
    Updater,
    UpdateStatus,
)

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

        self._delayed_info_timer: QTimer = QTimer(self, singleShot=True, interval=3000)
        _ = self._delayed_info_timer.timeout.connect(self._on_delayed_info_timeout)
        self._delayed_name: str | None = None
        self._delayed_desc: str | None = None
        self._delayed_icon: IconLoadMethod | None = None

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
        _ = self._progress2_anim.finished.connect(self.repaint)  # progress_anim repaints each frame

    def _on_update_info(self, _update_info: UpdateInfo) -> None:
        self._update_name_and_description()

    def _update_name_and_description(self) -> None:
        ui = self._updater.update_info

        name = "Check for update"
        desc = f"Checks if new version of {APPLICATION_NAME.title()} available."
        icon = IconLoadMethod(LoadMethod.default)

        if (er := self._updater.update_info.error) is not None:
            if isinstance(er, NetworkError):
                er_str = er.error_str
            else:
                er_str = str(er)
            desc2 = desc
            desc = (
                f"{self._updater.update_info.state.name.replace('_', ' ').title()} Error: {er_str}"
            )
            self._set_delayed_info(desc=desc2, interval=len(desc2) * 65)

            if ui.state in {UpdateStatus.update_checking, UpdateStatus.update_checked}:
                ui.state = UpdateStatus.none
            elif ui.state in {
                UpdateStatus.download_started,
                UpdateStatus.downloading,
                UpdateStatus.download_aborted,
            }:
                ui.state = UpdateStatus.update_checked
            elif ui.state in {
                UpdateStatus.installation_started,
                UpdateStatus.installing,
                UpdateStatus.installation_queue,
            }:
                ui.state = UpdateStatus.downloaded

        else:
            match ui.state:
                case UpdateStatus.none:
                    pass
                case UpdateStatus.update_checking:
                    name = "Check for update"
                    desc = f"Checking if new version of {APPLICATION_NAME.title()} available."
                    icon = IconLoadMethod(LoadMethod.loading)
                case UpdateStatus.update_checked:
                    if ui.update_available is None:
                        desc2 = desc  # default description after delay
                        desc = f"No new version of {APPLICATION_NAME.title()} available."
                    else:
                        name = f"Update {APPLICATION_NAME.title()}"
                        if ui.latest_release is None:  # if it is None unexpectedly
                            desc = f"New version of {APPLICATION_NAME.title()} available."
                            desc2 = (
                                f"Update {APPLICATION_NAME.title()} from {VERSION} to new version."
                            )
                        else:
                            desc = f"New version {ui.latest_release.tag_name} of {APPLICATION_NAME.title()} available."
                            desc2 = f"Update {APPLICATION_NAME.title()} from {VERSION} to {ui.latest_release.tag_name}."
                    self._set_delayed_info(desc=desc2, interval=len(desc2) * 65)
                    self._checked_update_timeout.stop()
                    self._checked_update_timeout.start()
                case UpdateStatus.download_started:
                    name = "Updating"
                    icon = IconLoadMethod(LoadMethod.loading)
                    desc = "Preparing download..."
                case UpdateStatus.downloading:
                    name = "Updating"
                    icon = IconLoadMethod(LoadMethod.loading)
                    dp = ui.download_progress
                    if dp is not None:
                        desc = self._build_download_state(dp)
                        self._update_progress_bar(dp.download_progress)
                    else:
                        desc = "Downloading"
                case UpdateStatus.downloaded:
                    name = "Updating"
                    desc = "Downloaded"
                case UpdateStatus.download_aborted:
                    desc2 = desc
                    desc = "Download aborted"
                    self._update_progress_bar(0.0)
                    self._set_delayed_info(desc=desc2, interval=len(desc2) * 65)
                case UpdateStatus.installation_queue:
                    name = "Updating"
                    desc = "Installation queue"
                case UpdateStatus.installation_started:
                    name = "Updating"
                    desc = "Preparing to install..."
                    icon = IconLoadMethod(LoadMethod.loading)
                    self._update_progress_bar(0.0)
                case UpdateStatus.installing:
                    name = "Updating"
                    ip = ui.install_progress
                    if ip is not None:
                        desc = f"Installing {ip.ratio * 100:.2f}%"
                        self._update_progress_bar(ip.ratio)
                    else:
                        desc = "Installing..."
                    icon = IconLoadMethod(LoadMethod.loading)
                case UpdateStatus.installed:
                    desc = "Installed"
                    self._update_progress_bar(0.0)
                case UpdateStatus.restart_queue:
                    name = f"Restart {APPLICATION_NAME.title()}"
                    desc = "Need restart"

        self.set_name(name)
        self.set_description(desc)
        self._icon.update_load_method(icon)

    @staticmethod
    def _build_download_state(download_state: Downloaded) -> str:
        x = "Downloaded" if download_state.completed else "Downloading"
        f = download_state.file_path.name
        d = readable_size(download_state.downloaded_size)
        t = readable_size(download_state.total_size)
        p = f"{download_state.download_progress * 100:.2f}%"
        s = f"{readable_size(download_state.speed)}/s" if download_state.speed is not None else ""
        # Downloading ProsperoSetup-0.0.1.exe    15MiB/40MiB (20.0%)    5MiB/s
        desc = f"{x} {f}    {d}/{t} ({p})    {s}"
        return desc

    def _set_delayed_info(
        self,
        name: str | None = None,
        desc: str | None = None,
        icon: IconLoadMethod | None = None,
        interval: int = 3000,
    ) -> None:
        if self._delayed_info_timer.isActive():
            self._delayed_info_timer.stop()
        self._delayed_name = name
        self._delayed_desc = desc
        self._delayed_icon = icon
        if any(x is not None for x in {name, desc, icon}):
            self._delayed_info_timer.setInterval(interval)
            self._delayed_info_timer.start()

    def _on_delayed_info_timeout(self) -> None:
        name, desc, icon = self._delayed_name, self._delayed_desc, self._delayed_icon
        if name is not None:
            self.set_name(name)
        if desc is not None:
            self.set_description(desc)
        if icon is not None:
            self._icon.update_load_method(icon)

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

    def _on_checked_update_timeout(self) -> None:
        self._updater.update_info.state = UpdateStatus.none

    @override
    def request_deletion(self) -> None:
        self.hide()

    @override
    def update_result(self, new_result: "BaseResult") -> None:
        # super().update_result(new_result)
        self.result = new_result  # pyright: ignore[reportUnannotatedClassAttribute]
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
