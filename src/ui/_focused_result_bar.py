from typing import cast, override

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget


class FocusResultBar(QWidget):
    _EASE_1: QEasingCurve = QEasingCurve(QEasingCurve.Type.OutExpo)
    _EASE_2: QEasingCurve = QEasingCurve(QEasingCurve.Type.Linear)

    def __init__(self, width: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._width: int = width
        self._height: int = 0
        self._mid_y: int = 0
        self.setFixedWidth(self._width)

        _ = self.setProperty("_point_1", 0.0)
        self._point_1_anim: QPropertyAnimation = QPropertyAnimation(self, b"_point_1", self)
        self._point_1_anim.setDuration(200)
        _ = self._point_1_anim.finished.connect(self.repaint)

        _ = self.setProperty("_point_2", 0.0)
        self._point_2_anim: QPropertyAnimation = QPropertyAnimation(self, b"_point_2", self)
        self._point_2_anim.setDuration(200)
        _ = self._point_2_anim.valueChanged.connect(self.repaint)

    def move_bar(self, mid_y: int) -> None:
        old = self._mid_y
        if old == mid_y:
            return
        self._mid_y = mid_y
        self._point_1_anim.stop()
        self._point_2_anim.stop()
        if old > mid_y:
            self._point_1_anim.setEasingCurve(QEasingCurve.Type.OutExpo)
            self._point_2_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        else:
            self._point_1_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self._point_2_anim.setEasingCurve(QEasingCurve.Type.OutExpo)
        self._adjust_points()

    def resize_bar(self, height: int) -> None:
        self._height = height
        self._adjust_points()

    def _adjust_points(self) -> None:
        """Calculates two points from mid pont and height of the bar and animate the points."""
        mid_point, height = self._mid_y, self._height
        half = height / 2
        p1 = mid_point - half
        p2 = mid_point + half

        self._point_1_anim.stop()
        self._point_2_anim.stop()
        self._point_1_anim.setEndValue(p1)
        self._point_2_anim.setEndValue(p2)
        self._point_1_anim.start()
        self._point_2_anim.start()

    @override
    def paintEvent(self, event: QPaintEvent, /) -> None:
        with QPainter(self) as p:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setBrush(self.palette().accent())
            p.setPen(Qt.PenStyle.NoPen)
            r = self._width / 2
            x = self.contentsRect().left()
            p1 = cast(int, self.property("_point_1"))
            p2 = cast(int, self.property("_point_2"))
            rect = QRect(x, p1, self._width, p2 - p1)
            p.drawRoundedRect(rect, r, r)
