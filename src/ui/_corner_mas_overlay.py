from typing import override

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPainterPath, QPaintEvent
from PySide6.QtWidgets import QWidget

from theme import theme


class CornerMaskOverlay(QWidget):
    """To cut corner radius shape from main window.

    This widget is just laid over the main window contents. This will draw transparent corners
    with composition mode of the painter set to source. which makes the corner curves.
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._radius: float | tuple[float, float, float, float]
        self._update_radius()
        theme.main_window.corner_radius.subscribe(self._update_radius)

    def _update_radius(self) -> None:
        cr = theme.main_window.corner_radius
        split = cr.split_values.value
        if split:
            self._radius = (
                cr.top_left.value,
                cr.top_right.value,
                cr.bottom_right.value,
                cr.bottom_left.value,
            )
        else:
            self._radius = cr.single_value.value
        self.repaint()

    @override
    def paintEvent(self, event: QPaintEvent, /) -> None:
        if isinstance(self._radius, tuple):
            a, b, c, d = self._radius
            draw = max(self._radius) > 0
        else:
            a = b = c = d = self._radius
            draw = self._radius > 0

        if draw:
            rect = self.rect().adjusted(0, 0, 1, 1)
            top_left_radius = a
            top_right_radius = b
            bottom_right_radius = c
            bottom_left_radius = d

            rounded_path = QPainterPath()
            "The path to be painted"

            # Start from top-left, after the corner arc
            rounded_path.moveTo(rect.left() + top_left_radius, rect.top())

            # Top edge & top-right corner
            rounded_path.lineTo(rect.right() - top_right_radius, rect.top())
            rounded_path.arcTo(
                rect.right() - (2 * top_right_radius),
                rect.top(),
                2 * top_right_radius,
                2 * top_right_radius,
                90,
                -90,
            )

            # Right edge & bottom-right corner
            rounded_path.lineTo(rect.right(), rect.bottom() - bottom_right_radius)
            rounded_path.arcTo(
                rect.right() - (2 * bottom_right_radius),
                rect.bottom() - (2 * bottom_right_radius),
                2 * bottom_right_radius,
                2 * bottom_right_radius,
                0,
                -90,
            )

            # Bottom edge & bottom-left corner (radius 0 means sharp line)
            rounded_path.lineTo(rect.left() + bottom_left_radius, rect.bottom())
            if bottom_left_radius > 0:
                rounded_path.arcTo(
                    rect.left(),
                    rect.bottom() - (2 * bottom_left_radius),
                    2 * bottom_left_radius,
                    2 * bottom_left_radius,
                    270,
                    -90,
                )

            # Left edge & top-left corner
            rounded_path.lineTo(rect.left(), rect.top() + top_left_radius)
            rounded_path.arcTo(
                rect.left(), rect.top(), 2 * top_left_radius, 2 * top_left_radius, 180, -90
            )

            rounded_path.closeSubpath()

            path = QPainterPath()
            "Path to be removed (corners)"
            path.addRect(rect)
            corners_path = path.subtracted(rounded_path)  # everything OUTSIDE the rounded rect

            with QPainter(self) as painter:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
                painter.fillPath(corners_path, Qt.GlobalColor.transparent)
