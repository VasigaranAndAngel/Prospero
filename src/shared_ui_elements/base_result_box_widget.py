from typing import override

from PySide6.QtCore import QEasingCurve, QMetaObject, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFocusEvent,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPalette,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from providers import BaseResult, ExecutionAction

from .icon import Icon


class BaseResultBoxWidget(QWidget):
    focus_request: Signal = Signal(QWidget)

    def __init__(self, text: str, result: "BaseResult", /, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._text: str = text
        self.result: "BaseResult" = result
        self.shadow_focus: bool = False
        self.description: str | None = result.description
        self.focus_request_connection: QMetaObject.Connection | None = None

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_shadow_focus(self, focus: bool) -> None:
        self.shadow_focus = focus

    def set_description(self, desc: str | None) -> None:
        raise NotImplementedError

    def request_deletion(self) -> None:
        """This will be called by MainWindow when this widget is no longer needed.

        If providers need to do something else instead deleting the widget, it can override this
        method to do so.
        """
        self.deleteLater()

    def execute_execution_action(self, action: "ExecutionAction") -> None:
        self.result.execute(action)

    def update_result(self, new_result: "BaseResult") -> None:
        self.result = new_result

    @override
    def keyReleaseEvent(self, event: QKeyEvent, /) -> None:
        if event.key() == Qt.Key.Key_Return:
            self.execute_execution_action(ExecutionAction.Trigger)
            event.accept()
            return
        return super().keyReleaseEvent(event)

    @override
    def mousePressEvent(self, event: QMouseEvent, /) -> None:
        self.focus_request.emit(self)
        return super().mousePressEvent(event)

    @override
    def mouseDoubleClickEvent(self, event: QMouseEvent, /) -> None:
        self.execute_execution_action(ExecutionAction.Trigger)
        event.accept()


class ResultBox(BaseResultBoxWidget):
    def __init__(self, text: str, result: "BaseResult", /, parent: QWidget | None = None) -> None:
        super().__init__(text, result, parent)

        self.setFixedHeight(60)

        self.setLayout(main_lay := QHBoxLayout())
        main_lay.setSpacing(10)
        main_lay.setContentsMargins(10, 10, 10, 10)

        main_lay.addWidget(icon := Icon(result.icon_load_method, self))
        icon.setFixedSize(40, 40)
        self._icon: Icon = icon

        main_lay.addLayout(txt_lay := QVBoxLayout())
        txt_lay.setContentsMargins(0, 0, 0, 0)
        txt_lay.setSpacing(0)
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

        self._name_widget: QLabel = name_label
        self._description_widget: QLabel = info_label
        font = name_label.font()
        font.setPointSize(int(font.pointSize() * 1.3))
        name_label.setFont(font)
        pal = info_label.palette()
        col = pal.buttonText().color()
        col.setAlphaF(0.9)
        pal.setColor(QPalette.ColorRole.ButtonText, col)
        info_label.setPalette(pal)

        self.set_description(self.description)

        _ = self.setProperty("_bg_color", QColor("transparent"))
        self._back_color_anim: QPropertyAnimation = QPropertyAnimation(self, b"_bg_color")
        self._back_color_anim.setDuration(400)
        self._back_color_anim.setEasingCurve(QEasingCurve.Type.OutExpo)
        _ = self._back_color_anim.valueChanged.connect(self.repaint)

    def _reflect_result(self) -> None:
        "Will update everything according to result. Useful if the result is updated."
        if self._icon.load_method() != self.result.icon_load_method:
            self._icon.update_load_method(self.result.icon_load_method)
        if self._name_widget.text() != self.result.text:
            self._name_widget.setText(self.result.text)
        if self._description_widget.text() != self.result.description:
            self.set_description(self.result.description)

    @override
    def update_result(self, new_result: "BaseResult") -> None:
        super().update_result(new_result)
        self._reflect_result()

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

    def set_name(self, name: str) -> None:
        self._name_widget.setText(name)

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
