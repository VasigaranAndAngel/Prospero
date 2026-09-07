"""BaseResult model, BaseResultBoxWidget, and ResultBox are implemented in here.

Tried moving ui related codes to separate shared modules and faced circular import issues. The final
decision is to put all related codes in same file. Now BaseResultBoxWidget and ResultBox widgets are
exported from providers.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import override

# TODO: This module will be imported on cli mode too. which imports unwanted PySide6
from PySide6.QtCore import QEasingCurve, QMetaObject, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QColor, QFocusEvent, QKeyEvent, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from data_objects import IconLoadMethod, LoadMethod
from shared_ui_elements import CustomVBoxLayout, Icon


def _get_default_icon() -> "IconLoadMethod":
    return IconLoadMethod(LoadMethod.default)


class ExecutionActions(Enum):
    Enter = auto()


@dataclass
class ResultAttributes:
    highlight_request: None = None
    "If need to highlight anything in query."
    suggestion_request: None = None
    "If anything is there to show as query suggestion."
    coloring_request: None = None
    "If need to colorized anything in query."
    close_after_enter: bool = False


@dataclass
class BaseResult:
    result: str
    score: int
    highlighted_indexes: list[int]
    description: str | None = None
    attributes: ResultAttributes = field(default_factory=ResultAttributes)
    icon_load_method: IconLoadMethod = field(default_factory=_get_default_icon)
    result_widget_factory: Callable[[str, "BaseResult"], "BaseResultBoxWidget"] | None = None

    def highlighted(self, open_tag: str = "**", close_tag: str = "**") -> str:
        ih = set(self.highlighted_indexes)
        return "".join(
            [f"{open_tag}{c}{close_tag}" if i in ih else f"{c}" for i, c in enumerate(self.result)]
        )

    def execute(self, action: ExecutionActions) -> None:  # pyright: ignore[reportUnusedParameter]
        raise NotImplementedError

    @override
    def __hash__(self) -> int:
        return hash(self.result + (self.description or ""))


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


class ResultBox(BaseResultBoxWidget):
    def __init__(self, text: str, result: BaseResult, /, parent: QWidget | None = None) -> None:
        super().__init__(text, result, parent)

        self.setFixedHeight(60)

        self.setLayout(main_lay := QHBoxLayout())
        main_lay.setSpacing(10)
        main_lay.setContentsMargins(10, 10, 10, 10)

        main_lay.addWidget(icon := Icon(result.icon_load_method, self))
        icon.setFixedSize(40, 40)

        main_lay.addLayout(txt_lay := CustomVBoxLayout())
        txt_lay.setContentsMargins(0, 0, 0, 0)
        txt_lay.setSpacing(0)
        txt_lay.duration = 500
        txt_lay.addWidget(name_label := QLabel(text, self), alignment=Qt.AlignmentFlag.AlignVCenter)
        txt_lay.addWidget(info_label := QLabel("", self), alignment=Qt.AlignmentFlag.AlignTop)
        info_label.hide()

        # NOTE: since the CustomVBoxLayout detects and animates geometry of widgets, we can change
        # the init values by altering the geometry.
        init_x = main_lay.contentsMargins().left() + main_lay.spacing()
        init_x += txt_lay.contentsMargins().left() + icon.width()
        init_y = self.height() // 2
        name_label.move(init_x, init_y - name_label.height() // 2)
        info_label.move(init_x, init_y - info_label.height() // 2)

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
        self.shadow_focus: bool = focus
        if focus:
            self._change_color(QColor("#10ff0000"))
        else:
            self._change_color(QColor("transparent"))

    @override
    def set_description(self, desc: str | None) -> None:
        self.description: str | None = desc
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


__all__ = ["ExecutionActions", "ResultAttributes", "BaseResult", "BaseResultBoxWidget", "ResultBox"]
