from collections.abc import Callable
from functools import partial
from typing import override

from PySide6.QtCore import QEasingCurve, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QHideEvent,
    QPainter,
    QPaintEvent,
    QPalette,
    QPolygonF,
    QShowEvent,
)
from PySide6.QtWidgets import QLineEdit, QWidget

from ._placeholder_formatter import PlaceholderFormatter as PhF


class QueryBox(QLineEdit):
    _start_loading_anim: Signal = Signal()
    "To update frames from main thread."
    _LOADING_LINE_WIDTH: float = 3
    _EASING_IN: QEasingCurve = QEasingCurve(QEasingCurve.Type.InOutExpo)
    _EASING_OUT: QEasingCurve = QEasingCurve(QEasingCurve.Type.InOutExpo)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._frame: int = 0
        "Current frame"
        self._render_line: bool = False
        "Whether the line should be rendered or not"
        self._fps: int = int(self.screen().refreshRate())
        "Frames count per second"
        self._frame_interval: int = 1000 // self._fps
        "Interval between each frame"
        self._anim_duration: int = 1200
        "Duration of single loop in ms"
        self._frame_count: int = int(self._fps * (self._anim_duration / 1000))
        "Total frames count for single loop"
        self._placeholder: str | bool = True
        "Query placeholder. True: auto calculated; False: no placeholder; str: Custom placeholder."
        self._placeholder_alignment: Qt.AlignmentFlag = (
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
        )
        self._placeholder_txt: str = ""
        self._placeholder_formatter: PhF = PhF(r"{time:{h}:{mm}:{ss} {A}}", self)
        "Placeholder formatter."

        # Initialize placeholder based on the configured _placeholder value
        self._update_placeholder()
        _ = self._placeholder_formatter.updated.connect(self._update_placeholder)
        self._placeholder_formatter.start()

        # Update frame metrics to match with new refresh rate of the screen
        # TODO: connect to new screen's refreshRateChanged when screen is changed
        _ = self.screen().refreshRateChanged.connect(self._update_frame_metrics)

        self._loading_state: bool = False
        self._screen_change_connection_disconnect: Callable[[], bool] | None = None

        self.setFixedHeight(60)
        self.setContentsMargins(10, 10, 10, 10)

        self._suggestion: str | None = None
        "The full suggestion text."
        self._suggestion_render_text: str = ""
        "Part of suggestion text which will be rendered."
        _ = self.textChanged.connect(self._update_suggestion)

        font = self.font()
        font.setPointSize(int(font.pointSize() * 1.4))
        self.setFont(font)

        self.setFrame(False)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Base, "transparent")
        self.setPalette(pal)

        _ = self._start_loading_anim.connect(self._next_frame)

    def _update_frame_metrics(self) -> None:
        self._fps = min(int(self.screen().refreshRate()), 120)  # maximum fps is 120
        self._frame_interval = 1000 // self._fps
        self._frame_count = int(self._fps * (self._anim_duration / 1000))

    def _next_frame(self) -> None:
        if self._frame >= self._frame_count:
            self._frame = 0
        else:
            self._frame += 1

        if self._frame in {self._frame_count // 2, self._frame_count} and not self._loading_state:
            self._render_line = False
        else:
            QTimer.singleShot(self._frame_interval, self._next_frame)

        self.repaint()

    def _update_placeholder(self, text: str = "") -> None:
        old_txt = self._placeholder
        if isinstance(self._placeholder, str):
            self._placeholder_txt = self._placeholder
        elif self._placeholder:
            self._placeholder_txt = text
        else:
            self._placeholder_txt = ""
        if old_txt != self._placeholder_txt:
            self.repaint()

    def _update_suggestion(self, new_txt: str | None = None) -> None:
        sug = self._suggestion
        txt = new_txt or self.text()
        if sug is not None and txt and sug.casefold().startswith(txt):
            self._suggestion_render_text = sug[len(txt) :]
        else:
            self._suggestion_render_text = ""
        self.repaint()

    def set_loading_state(self, state: bool) -> None:
        if not self._loading_state and state:
            if not self._render_line:
                self._render_line = True
                self._start_loading_anim.emit()
        self._loading_state = state

    def set_suggestion(self, sug: str) -> None:
        self._suggestion = sug
        self._update_suggestion()

    @override
    def showEvent(self, event: QShowEvent, /) -> None:
        super().showEvent(event)

        # make sure there are no connection left connected in case showEvent triggered multiple times
        if self._screen_change_connection_disconnect is not None:
            _ = self._screen_change_connection_disconnect()
            self._screen_change_connection_disconnect = None

        # connect screenChanged to update_frame_metrics and store disconnect function with connection
        scrn_hdl = self.windowHandle()
        # scrn_hdl could be None
        if scrn_hdl is not None:  # pyright: ignore[reportUnnecessaryComparison]
            scrn_change = scrn_hdl.screenChanged
            connection = scrn_change.connect(self._update_frame_metrics)
            self._screen_change_connection_disconnect = partial(scrn_change.disconnect, connection)

    @override
    def hideEvent(self, event: QHideEvent, /) -> None:
        # make sure the screenChanged connection is disconnected before hide event
        if self._screen_change_connection_disconnect is not None:
            _ = self._screen_change_connection_disconnect()
            self._screen_change_connection_disconnect = None
        super().hideEvent(event)

    @override
    def paintEvent(self, arg__1: QPaintEvent, /) -> None:
        super().paintEvent(arg__1)
        if self._render_line:
            ls = 1 / self._frame_count * self._frame
            le = ls - 0.13

            if ls < 0.5:
                ls = type(self)._EASING_OUT.valueForProgress(ls * 2)
            else:
                ls = type(self)._EASING_IN.valueForProgress(2 - ls * 2)

            if le < 0.5:
                le = type(self)._EASING_OUT.valueForProgress(le * 2)
            else:
                le = type(self)._EASING_IN.valueForProgress(2 - le * 2)

            l_width = type(self)._LOADING_LINE_WIDTH / 2
            start_p = self.rect().bottomLeft().toPointF()
            end_p = self.rect().bottomRight().toPointF()
            polygon = QPolygonF(
                [
                    QPointF(end_p.x() * le, start_p.y()),
                    QPointF(end_p.x() * ls, end_p.y() + l_width),
                    QPointF(end_p.x() * ls, end_p.y() - l_width),
                    QPointF(end_p.x() * le, start_p.y()),
                ]
            )
            with QPainter(self) as p:
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor(30, 144, 255)))
                p.drawPolygon(polygon)
                p.drawEllipse(QPointF(end_p.x() * ls, end_p.y()), l_width, l_width)

        if self._placeholder:
            with QPainter(self) as p:
                t = self._placeholder_txt
                a = self._placeholder_alignment
                p.setPen(self.palette().placeholderText().color())
                p.drawText(self.contentsRect().adjusted(0, 0, 0, 0), t, a)

        if self._suggestion_render_text:
            with QPainter(self) as p:
                cr = self.contentsRect()
                fm = p.fontMetrics()
                x = cr.left() + fm.size(0, self.text()).width() + 6  # Not sure about this 6
                mid_y = cr.height() // 2
                y = mid_y + fm.ascent()
                p.setPen(self.palette().placeholderText().color())
                p.drawText(x, y, self._suggestion_render_text)
