
from typing import override

from PySide6.QtCore import QMetaObject, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QWidget

from providers import BaseResult, ExecutionActions


class BaseResultBoxWidget(QWidget):
    focus_request: Signal = Signal(QWidget)

    def __init__(self, text: str, result: BaseResult, /, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._text: str = text
        self.result: BaseResult = result
        self.shadow_focus: bool = False
        self.description: str | None = result.description
        self.focus_request_connection: QMetaObject.Connection | None = None

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_shadow_focus(self, focus: bool) -> None:
        self.shadow_focus = focus

    def set_description(self, desc: str | None) -> None:
        raise NotImplementedError

    @override
    def keyReleaseEvent(self, event: QKeyEvent, /) -> None:
        if event.key() == Qt.Key.Key_Return:
            self.result.execute(ExecutionActions.Enter)
            event.accept()
            return
        return super().keyReleaseEvent(event)

    @override
    def mousePressEvent(self, event: QMouseEvent, /) -> None:
        self.focus_request.emit(self)
        return super().mousePressEvent(event)

