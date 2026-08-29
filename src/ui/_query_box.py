from typing import override

from PySide6.QtGui import QPainter, QPaintEvent, Qt
from PySide6.QtWidgets import QLineEdit, QWidget


class QueryBox(QLineEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._loading_state: bool = False

        self.setFixedHeight(60)
        self.setContentsMargins(10, 10, 10, 10)

        font = self.font()
        font.setPointSize(int(font.pointSize() * 1.4))
        self.setFont(font)

        self.setStyleSheet('QLineEdit {background: "transparent"; border: "transparent"}')

    def set_loading_state(self, state: bool) -> None:
        self._loading_state = state
        self.repaint()

    @override
    def paintEvent(self, arg__1: QPaintEvent, /) -> None:
        super().paintEvent(arg__1)
        if self._loading_state:
            with QPainter(self) as p:
                p.setPen("white")
                p.setBrush(Qt.BrushStyle.NoBrush)
                r = self.rect()
                p.drawLine(r.bottomLeft(), r.bottomRight())
