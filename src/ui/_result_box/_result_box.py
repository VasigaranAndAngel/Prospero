from typing import override

from PySide6.QtCore import (
    QEasingCurve,
    QMetaObject,
    QPropertyAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFocusEvent,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    Qt,
)
from PySide6.QtWidgets import QLabel, QWidget

from providers import BaseResult, ExecutionActions

from ._layout import CustomVBoxLayout


class ResultBox(QWidget):
    focus_request: Signal = Signal(QWidget)

    def __init__(self, text: str, result: BaseResult, /, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._text: str = text
        self.result: BaseResult = result
        self.shadow_focus: bool = False
        self._description: str | None = result.description
        self.focus_request_connection: QMetaObject.Connection | None = None

        self.setFixedHeight(60)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

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

        self.set_description(self._description)

        _ = self.setProperty("_bg_color", QColor("transparent"))
        self._back_color_anim: QPropertyAnimation = QPropertyAnimation(self, b"_bg_color")
        self._back_color_anim.setDuration(400)
        self._back_color_anim.setEasingCurve(QEasingCurve.Type.OutExpo)
        _ = self._back_color_anim.valueChanged.connect(self.repaint)

    def set_shadow_focus(self, focus: bool) -> None:
        self.shadow_focus = focus
        if focus:
            self._change_color(QColor("#10ff0000"))
        else:
            self._change_color(QColor("transparent"))

    def set_description(self, desc: str | None) -> None:
        self._description = desc
        if desc is None:
            self._description_widget.setText("")
            self._description_widget.hide()
        else:
            self._description_widget.setText(desc)
            self._description_widget.show()

    # region TODO Remove
    # def _detach_window(self) -> None:  
    #     pos = self.mapToGlobal(self.pos())
    #     self.setParent(None)

    #     self.setWindowFlag(Qt.WindowType.Tool, True)  # Removes alt+space popup system menu
    #     self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    #     self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

    #     self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    #     self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)

    #     self.show()
    #     self.move(pos)

    # def _init_shadow_widget(self) -> None:
    #     pixmap = self.grab()
    #     wid = QLabel(self)

    #     self.setWindowFlag(Qt.WindowType.Tool, True)  # Removes alt+space popup system menu
    #     self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    #     self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

    #     self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    #     self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)

    #     wid.setPixmap(pixmap)
    #     wid.show()
    #     wid.move(self.mapToGlobal(self.pos()))

    # def _duplicate_me(self) -> None:
    #     new = ResultBox(self._text, self.result)
    #     new.setWindowFlag(Qt.WindowType.Tool, True)
    #     new.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    #     new.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

    #     new.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    #     new.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
    #     new.layout().animate = False
    #     new.set_shadow_focus(True)
    #     new.show()
    #     new.move(self.mapToGlobal(self.pos()))
    #     new.resize(self.size())
        
    #     # anim = QVariantAnimation(new, startValue=new.width(), endValue=0)
    #     anim = QVariantAnimation(new, startValue=new.geometry(), endValue=0)
    #     # anim = QPropertyAnimation(new, b"geometry", new)
    #     anim.setEndValue(new.geometry().adjusted((x := new.width() // 2), -10, -x, 10))
    #     anim.setDuration(750)
    #     anim.setEasingCurve(QEasingCurve.Type.OutExpo)
    #     _ = anim.valueChanged.connect(lambda x: new.setFixedWidth(x.width()))
    #     _ = anim.valueChanged.connect(lambda x: new.move(x.x(), x.y()))
    #     # _ = anim.valueChanged.connect(new.setFixedWidth)
    #     _ = anim.finished.connect(new.close)
    #     _ = anim.finished.connect(new.deleteLater)
    #     anim.start()
    #     self._new = new
    # endregion

    @override
    def focusInEvent(self, event: QFocusEvent, /) -> None:
        self._change_color(QColor("#10ff0000"))
        return super().focusInEvent(event)

    @override
    def focusOutEvent(self, event: QFocusEvent, /) -> None:
        self._change_color(QColor("transparent"))
        return super().focusOutEvent(event)

    @override
    def keyReleaseEvent(self, event: QKeyEvent, /) -> None:
        if event.key() == Qt.Key.Key_Return:
            print("Enter key release event: triggering execution")  # TODO: remove
            self.result.execute(ExecutionActions.Enter)
            event.accept()
            # self._detach_window()
            # self._init_shadow_widget()
            # self._duplicate_me()
            return
        return super().keyReleaseEvent(event)

    @override
    def mousePressEvent(self, event: QMouseEvent, /) -> None:
        self.focus_request.emit(self)
        return super().mousePressEvent(event)

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
