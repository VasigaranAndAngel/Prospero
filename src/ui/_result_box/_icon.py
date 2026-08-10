"""
TODO: Notices memory leak kind of issue. sometimes, it uses upto 2GB of ram when only checking Icon\
widget. Check and make sure there are no memory leak kind of issues. Known suspect is storing\
QPixmaps in a dict in _SpinnerFrames.
"""

import math
from enum import Enum, auto
from typing import override

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QHideEvent,
    QImage,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPixmap,
    QPolygonF,
    QShowEvent,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QLabel, QWidget

import assets
import helpers
from data_objects import IconLoadMethod
from global_threading import THREAD_POOL


class _DefaultSvgRenderer(QSvgRenderer):
    _instance: "_DefaultSvgRenderer | None" = None
    _initialized: bool = False

    def __new__(cls) -> "_DefaultSvgRenderer":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        super().__init__(assets.DEFAULT_RESULT_ICON_PATH.as_posix())
        self._initialized = True


def _draw_arc(
    painter: QPainter,
    width: int,
    height: int,
    start_t: float,
    end_t: float,
    segments: int,
    radius: float,
    min_width: float,
    max_width: float,
) -> None:
    cx, cy = width / 2, height / 2

    start_t = start_t + 0.75
    end_t = end_t + 0.75
    angle0 = start_t * 2 * math.pi
    sweep = (end_t - start_t) % 1.0
    if sweep == 0:
        sweep = 1.0  # treat equal start/end as a full loop
    sweep_rad = sweep * 2 * math.pi

    outer_pts: list[QPointF] = []
    inner_pts: list[QPointF] = []
    end_center = None
    start_width = None

    for i in range(segments + 1):
        t = i / segments  # 0 at start cap, 1 at tapered tip
        angle = angle0 + t * sweep_rad

        # w = self.max_width + (self.min_width - self.max_width) * t
        w = min_width + (max_width - min_width) * t

        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)

        nx, ny = math.cos(angle), math.sin(angle)

        outer_pts.append(QPointF(x + nx * w / 2, y + ny * w / 2))
        inner_pts.append(QPointF(x - nx * w / 2, y - ny * w / 2))

        if i == segments:
            end_center = QPointF(x, y)
            start_width = w

    polygon_pts = outer_pts + inner_pts[::-1]

    path = QPainterPath()
    path.addPolygon(QPolygonF(polygon_pts))
    path.closeSubpath()

    color = QColor(30, 144, 255)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(color))
    painter.drawPath(path)

    # round cap at the starting point
    if start_width is not None and end_center is not None:
        r = start_width / 2
        painter.drawEllipse(end_center, r, r)


class _SpinnerFrames:
    _sheet: dict[int, QPixmap] = {}
    "Contains sheets. size is the key."
    MIN_WIDTH: float = 0
    MAX_WIDTH: float = 0.13

    @classmethod
    def _render_sheet(cls, frame_size: int, fps: int) -> QPixmap:
        curvet = QEasingCurve.Type.InOutExpo
        curve1 = QEasingCurve(curvet)
        curve2 = QEasingCurve(curvet)

        maw = frame_size * cls.MAX_WIDTH
        miw = cls.MIN_WIDTH
        fs = frame_size
        n = fps
        sheet = QPixmap(fs * n, fs)
        sheet.fill(Qt.GlobalColor.transparent)
        painter = QPainter(sheet)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for i in range(n):
            t = i / n
            st = curve1.valueForProgress(t) * 2
            et = curve2.valueForProgress((t + 0.09) % 1.0) * 2
            painter.save()
            painter.translate(i * fs, 0)
            _draw_arc(
                painter=painter,
                width=fs,
                height=fs,
                start_t=st,
                end_t=et,
                segments=60,
                radius=(fs - maw) / 2,
                min_width=miw,
                max_width=maw,
            )
            painter.restore()
        _ = painter.end()
        return sheet

    @classmethod
    def get_sheet(cls, frame_size: int, fps: int) -> QPixmap:
        if frame_size not in cls._sheet:
            cls._sheet[frame_size] = cls._render_sheet(frame_size, fps)
        return cls._sheet[frame_size]


class _IconState(Enum):
    Default = auto()
    Loading = auto()
    Loaded = auto()


class Icon(QLabel):
    _image_loaded: Signal = Signal(object)
    _instances: int = 0

    def __init__(self, icon_load_method: IconLoadMethod, parent: QWidget | None = None) -> None:
        super().__init__()

        Icon._instances += 1
        self._instance_no: int = Icon._instances

        self._load_method: IconLoadMethod = icon_load_method

        self._current_state: _IconState = _IconState.Loading
        # NOTE: fps is not dynamic. it will be fixed to primary monitors fps when creating instance.
        self._loading_fps: int = int(QApplication.primaryScreen().refreshRate())
        self._loading_frame: int = 0
        self._reset_loading_frame()

        # NOTE: current implementation creates QTimer instance and runs on each widget. in case if
        # optimization required, consider using single QTimer instance for all Icon instances.
        self._loading_timer: QTimer = QTimer(self)
        self._loading_timer.setInterval(1000 // self._loading_fps)
        _ = self._loading_timer.timeout.connect(self._next_frame)

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _ = self._image_loaded.connect(self._on_loaded)
        self._set_state(_IconState.Loading)
        _ = THREAD_POOL.apply_async(self._load_icon)

    def _load_icon(self) -> None:
        ic = None
        try:
            lm, path = self._load_method.load_method, self._load_method.file_path
            if path is None or lm in {"default", "loading"}:
                pass  # let ic to be None
            elif lm == "win32api":
                ic = helpers.fetch_icon(path)
            elif lm == "win32api_generic":
                ic = helpers.fetch_icon(path, use_generic_type=True)
            elif lm == "load_file":
                ic = QImage(path)
        except Exception:
            ic = None
        self._image_loaded.emit(ic)

    def _on_loaded(self, image: QImage | None) -> None:
        if image is None:
            if self._load_method.load_method == "loading":
                self._set_state(_IconState.Loading)
            else:
                self._set_state(_IconState.Default)
        else:
            self._set_state(_IconState.Loaded)
            self.setPixmap(QPixmap(image))

    def _set_state(self, state: _IconState) -> None:
        self._current_state = state
        if state is _IconState.Loading:
            self._loading_timer.start()
        else:
            self._loading_timer.stop()
            self._reset_loading_frame()
            self.repaint()

    def _next_frame(self) -> None:
        if self._loading_frame > self._loading_fps - 2:
            self._loading_frame = 0
        else:
            self._loading_frame += 1
        self.repaint()

    def _reset_loading_frame(self) -> None:
        self._loading_frame = self._instance_no * -2 % self._loading_fps - 2  # to add variations

    @override
    def showEvent(self, event: QShowEvent, /) -> None:
        if self._current_state is _IconState.Loading:
            self._loading_timer.start()
        return super().showEvent(event)

    @override
    def hideEvent(self, event: QHideEvent, /) -> None:
        self._loading_timer.stop()
        return super().hideEvent(event)

    @override
    def paintEvent(self, arg__1: QPaintEvent, /) -> None:
        if self._current_state is _IconState.Loaded:
            return super().paintEvent(arg__1)

        if self._current_state is _IconState.Loading:
            f = self._loading_frame
            fs = (self.width() + self.height()) // 2
            with QPainter(self) as p:
                src = QRectF(fs * f, 0, fs, fs)
                p.drawPixmap(
                    self.rect().toRectF(), _SpinnerFrames.get_sheet(fs, self._loading_fps), src
                )
        elif self._current_state is _IconState.Default:
            with QPainter(self) as p:
                _DefaultSvgRenderer().render(p)
