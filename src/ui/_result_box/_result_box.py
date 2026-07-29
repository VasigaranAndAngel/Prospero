from typing import final, override

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
)
from PySide6.QtGui import (
    QColor,
    QFocusEvent,
    QPainter,
    QPaintEvent,
    Qt,
)
from PySide6.QtWidgets import QLabel, QWidget

from providers import BaseResult

from ._base_result_box_widget import BaseResultBoxWidget
from ._layout import CustomVBoxLayout


@final
class ResultBox(BaseResultBoxWidget):
    def __init__(self, text: str, result: BaseResult, /, parent: QWidget | None = None) -> None:
        super().__init__(text, result, parent)

        self.setFixedHeight(60)

        self.setLayout(lay := CustomVBoxLayout(self))
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(0)
        lay.addWidget(name_label := QLabel(text, self), alignment=Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(info_label := QLabel("", self), alignment=Qt.AlignmentFlag.AlignTop)
        info_label.hide()
        self._description_widget: QLabel = info_label
        font = name_label.font()
        font.setPointSize(int(font.pointSize() * 1.3))
        name_label.setFont(font)
        info_label.setStyleSheet("QLabel {color: #b0ffffff}")

        self.set_description(self.description)

        _ = self.setProperty("_bg_color", QColor("transparent"))
        self._back_color_anim: QPropertyAnimation = QPropertyAnimation(self, b"_bg_color")
        self._back_color_anim.setDuration(400)
        self._back_color_anim.setEasingCurve(QEasingCurve.Type.OutExpo)
        _ = self._back_color_anim.valueChanged.connect(self.repaint)

    @override
    def set_shadow_focus(self, focus: bool) -> None:
        self.shadow_focus = focus
        if focus:
            self._change_color(QColor("#10ff0000"))
        else:
            self._change_color(QColor("transparent"))

    @override
    def set_description(self, desc: str | None) -> None:
        self.description = desc
        if desc is None:
            self._description_widget.setText("")
            self._description_widget.hide()
        else:
            self._description_widget.setText(desc)
            self._description_widget.show()

    @override
    def focusInEvent(self, event: QFocusEvent, /) -> None:
        self._change_color(QColor("#10ff0000"))
        return super().focusInEvent(event)

    @override
    def focusOutEvent(self, event: QFocusEvent, /) -> None:
        self._change_color(QColor("transparent"))
        return super().focusOutEvent(event)

    def _change_color(self, color: QColor) -> None:
        self._back_color_anim.stop()
        self._back_color_anim.setEndValue(color)
        self._back_color_anim.start()

    @override
    def paintEvent(self, event: QPaintEvent, /) -> None:
        with QPainter(self) as p:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self.property("_bg_color"))  # pyright: ignore[reportAny]
            p.drawRect(self.rect().adjusted(0, 0, -1, -1))
