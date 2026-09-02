import ctypes
import logging
from collections.abc import Collection
from typing import Literal, cast, override

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QResizeEvent,
)
from PySide6.QtWidgets import QVBoxLayout, QWidget

from config_models import ChangeEvent
from configs import conf
from providers import LoadingRequest, search_async
from providers._base_result import BaseResult
from theme import theme

from ._query_box import QueryBox
from ._result_box import ResultBox
from ._result_box._layout import CustomVBoxLayout
from ._results_box import ResultsBox

logger = logging.getLogger(__name__)


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
            rect = self.rect()
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


class MainWindow(QWidget):
    _result_update: Signal = Signal()
    "To update the results from the main thread."

    def __init__(self) -> None:
        super().__init__()

        self.setWindowFlag(Qt.WindowType.Tool, True)  # Removes alt+space popup system menu
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        # self.setWindowFlag(
        #     Qt.WindowType.WindowSystemMenuHint, False
        # )  # still shows the atl+space popup
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._result_boxes: list[ResultBox] = []
        self._shadow_focused_idx: int | None = None
        self._mouse_pressed: QPoint | None = None
        self._loading_requests: list[LoadingRequest] = []

        self._close: bool = False
        "Whether close the window when width anim finished."
        self._current_results: tuple[BaseResult, ...] = tuple()
        "All the results from current query."
        self._pos: QPoint = QPoint((x := self.screen().size()).width() // 2, x.height() // 3)
        "The position of the widget. (x points to middle of widget x)"

        self._corner_mask: CornerMaskOverlay = CornerMaskOverlay(self)
        self._corner_mask.show()

        self._query_box: QueryBox = QueryBox(self)
        _ = self._query_box.textChanged.connect(self._on_query_update)

        self._results_box: ResultsBox = ResultsBox(self)
        self._results_box.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._results_box.setStyleSheet(
            "QScrollArea {background: 'transparent'; border: 'transparent'}"
        )
        self._results_box.setWidget(wid := QWidget(self._results_box))
        self._results_box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        wid.setLayout(lay := CustomVBoxLayout(wid))
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._query_box, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._results_box)

        self.setLayout(layout)
        self._corner_mask.raise_()

        _ = self.setProperty("_width", 0)
        self._width_anim: QPropertyAnimation = QPropertyAnimation(self, b"_width")
        _ = self._width_anim.valueChanged.connect(self._update_geo)
        _ = self._width_anim.finished.connect(self._on_width_anim_finished)

        _ = self.setProperty("_height", 0)
        self._height_anim: QPropertyAnimation = QPropertyAnimation(self, b"_height")
        self._height_anim.setDuration(350)
        self._height_anim.setEasingCurve(QEasingCurve.Type.OutExpo)
        _ = self._height_anim.valueChanged.connect(self._update_geo)

        self._connect_config_hooks()
        self._update_pos()  # for update the position from config for the first time
        _ = self._result_update.connect(self._update_results_box)

    def _on_query_update(self, query: str) -> None:
        self._current_results = tuple()
        search_async(query, self._update_results)

    def _update_results(self, res: Collection[BaseResult] | LoadingRequest) -> None:
        if isinstance(res, LoadingRequest):
            self._loading_requests.append(res)
            res.add_to_remove_hooks(self._remove_loading_request)
            self._update_loading_state()
            return

        new_results = tuple(
            sorted(
                filter(lambda x: x.score > 0, self._current_results + tuple(res)),
                key=lambda x: -x.score,
            )
        )
        if not self._current_results or self._current_results != new_results:
            # Only update if results are empty or new results has changes.
            self._current_results = new_results
            self._result_update.emit()

    def _update_results_box(self) -> None:
        self._result_boxes = []
        widget = self._results_box.widget()
        if widget is None:
            raise Exception(
                f"Not able to update results box since self._results_box.widget() is None unexpectedly."
            )
        layout = cast(CustomVBoxLayout | None, widget.layout())
        if layout is None:
            raise Exception(
                f"Not able to update results box since self._results_box.widget().layout() is None unexpectedly."
            )

        # Preserve same hash results
        preserved: dict[int, ResultBox] = {}
        new_hashes = [hash(x) for x in self._current_results]
        # calc_in_new = any([lambda x: x.name == "Calculation Provider" for x in self._current_results])

        # Remove all old widgets.
        while layout.count() > 0:
            item = layout.itemAt(0)
            if item is None:
                continue
            wid = cast(ResultBox | None, item.widget())  # type of child widgets are ResultBox
            if wid is None:
                continue
            layout.removeWidget(wid)
            # check hash for same result
            if (x := hash(wid.result)) in new_hashes:
                preserved[x] = wid
                continue
            # disconnect focus request connections
            if (con := wid.focus_request_connection) is not None:
                _ = wid.focus_request.disconnect(con)
            wid.deleteLater()

        # Add new widgets
        for res in self._current_results:
            if (x := hash(res)) in preserved:
                res_box = preserved[x]
            else:
                res_box = ResultBox(res.result, res)
                res_box.setMinimumWidth(self.width())
                layout.newly_added_widgets.append(res_box)
                connection = res_box.focus_request.connect(self._on_focus_request)
                res_box.focus_request_connection = connection
            layout.addWidget(res_box)
            res_box.show()
            self._result_boxes.append(res_box)

        # Set window's size
        widget.adjustSize()
        self._update_size()

        # Remove old shadow focus
        for res_box in self._result_boxes:
            if res_box.shadow_focus:
                res_box.set_shadow_focus(False)
                break  # assuming only one result box was shadow focused

        # Set the shadow focus to first result.
        if self._result_boxes:
            self._shadow_focused_idx = 0
            for res_box in self._result_boxes:
                if res_box.shadow_focus:
                    self._shadow_focused_idx = self._result_boxes.index(res_box)
            self._result_boxes[self._shadow_focused_idx].set_shadow_focus(True)
        else:
            self._shadow_focused_idx = None

        # raise the mask widget to the top
        self._corner_mask.raise_()

    def _on_width_anim_finished(self) -> None:
        if self._close:
            _ = self.close()

    def _shadow_change_focus(self, to: Literal["next", "prev"]) -> None:
        if self._shadow_focused_idx is None:
            self._shadow_focused_idx = 0
        else:
            self._result_boxes[self._shadow_focused_idx].set_shadow_focus(False)

        if not self._result_boxes:
            self._shadow_focused_idx = None
            return

        elif to == "next":
            if self._shadow_focused_idx < len(self._result_boxes) - 1:
                self._shadow_focused_idx += 1
            else:
                self._shadow_focused_idx = 0
        elif to == "prev":
            if self._shadow_focused_idx > 0:
                self._shadow_focused_idx -= 1
            else:
                self._shadow_focused_idx = len(self._result_boxes) - 1

        self._result_boxes[self._shadow_focused_idx].set_shadow_focus(True)

    def _on_focus_request(self, widget: ResultBox) -> None:
        idx = self._result_boxes.index(widget)
        if self._shadow_focused_idx is not None:
            self._result_boxes[self._shadow_focused_idx].set_shadow_focus(False)

        self._shadow_focused_idx = idx
        self._result_boxes[self._shadow_focused_idx].set_shadow_focus(True)

    def _connect_config_hooks(self) -> None:
        conf.window_geometry.position.subscribe(self._update_pos)
        conf.window_geometry.size.subscribe(self._update_size)

    def _remove_loading_request(self, req: LoadingRequest) -> None:
        if req in self._loading_requests:
            self._loading_requests.remove(req)
            req.remove_from_remove_hooks(self._remove_loading_request)
        self._update_loading_state()

    def _update_loading_state(self) -> None:
        self._query_box.set_loading_state(len(self._loading_requests) > 0)

    # region config updates
    def _update_pos(self, _: ChangeEvent | None = None) -> None:
        s = self.screen().size()
        new_pos = QPoint(*conf.window_geometry.position.get_pos(s.width(), s.height()))

        if self._pos != new_pos:
            self._pos = new_pos
            self._update_geo()

    # endregion

    @override
    def keyPressEvent(self, event: QKeyEvent, /) -> None:
        if event.key() in {Qt.Key.Key_Up, Qt.Key.Key_Backtab}:
            self._shadow_change_focus("prev")
            self._query_box.grabKeyboard()
            event.accept()
            return
        elif event.key() in {Qt.Key.Key_Down, Qt.Key.Key_Tab}:
            self._shadow_change_focus("next")
            self._query_box.grabKeyboard()
            event.accept()
            return
        elif self._shadow_focused_idx is not None:
            self._result_boxes[self._shadow_focused_idx].keyPressEvent(event)
        return super().keyPressEvent(event)

    @override
    def keyReleaseEvent(self, event: QKeyEvent, /) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._despawn()
            event.accept()
            return
        if self._shadow_focused_idx is not None:
            res_box = self._result_boxes[self._shadow_focused_idx]
            res_box.keyReleaseEvent(event)
            if event.key() == Qt.Key.Key_Return and res_box.result.attributes.close_after_enter:
                self._despawn()
        return super().keyReleaseEvent(event)

    @override
    def mousePressEvent(self, event: QMouseEvent, /) -> None:
        self._mouse_pressed = event.pos()
        return super().mousePressEvent(event)

    @override
    def mouseMoveEvent(self, event: QMouseEvent, /) -> None:
        if self._mouse_pressed is not None:
            self._pos += event.pos() - self._mouse_pressed
            if conf.window_geometry.position.remember.value:
                s = self.screen().size()
                p = self._pos
                conf.window_geometry.position.set_pos(s.width(), s.height(), p.x(), p.y())
            self._update_geo()
        return super().mouseMoveEvent(event)

    @override
    def mouseReleaseEvent(self, event: QMouseEvent, /) -> None:
        self._mouse_pressed = None
        if conf.window_geometry.position.remember.value:
            conf.save_configs()
        return super().mouseReleaseEvent(event)

    def _update_geo(self) -> None:
        width = cast(int, self.property("_width"))
        height = cast(int, self.property("_height"))
        x = self._pos.x() - width // 2
        y = self._pos.y()
        self.setGeometry(x, y, width, height)

    def _force_foreground(self, hwnd: int):
        user32 = ctypes.windll.user32
        fg_hwnd = user32.GetForegroundWindow()  # pyright: ignore[reportAny]
        if not fg_hwnd:
            user32.SetForegroundWindow(hwnd)
            return
        fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None)  # pyright: ignore[reportAny]
        current_thread = ctypes.windll.kernel32.GetCurrentThreadId()  # pyright: ignore[reportAny]
        if fg_thread == current_thread:
            user32.SetForegroundWindow(hwnd)
            return
        user32.AttachThreadInput(fg_thread, current_thread, True)
        try:
            user32.SetForegroundWindow(hwnd)
        finally:
            user32.AttachThreadInput(fg_thread, current_thread, False)

    def _update_size(self) -> None:
        "Updates the size of window according to configs and spawn state with animation"
        src_s = self.screen().size()
        size = conf.window_geometry.size.get_size(src_s.width(), src_s.height())
        width = 0 if self._close else size[0]
        rw = self._results_box.widget()
        if rw is None:
            raise Exception(
                "Not able to update size since self._results_box.widget() is None unexpectedly."
            )
        height = min(rw.height() + self._query_box.height(), size[1])

        if self.width() != width:
            self._width_anim.stop()
            self._width_anim.setEndValue(width)
            self._width_anim.start()
        if self.height() != height:
            self._height_anim.stop()
            self._height_anim.setEndValue(height)
            self._height_anim.start()

    @override
    def show(self, /) -> None:
        self._close = False
        super().show()
        self._force_foreground(self.winId())
        self.raise_()
        QTimer.singleShot(1, self.activateWindow)
        self._query_box.setFocus()
        self._query_box.selectAll()

        self._width_anim.stop()
        self._width_anim.setEasingCurve(QEasingCurve.Type.OutExpo)
        self._width_anim.setDuration(200)
        self._update_size()

    def _despawn(self) -> None:
        self._close = True
        self._width_anim.stop()
        self._width_anim.setEasingCurve(QEasingCurve.Type.InExpo)
        self._width_anim.setDuration(100)
        self._update_size()

    @override
    def event(self, event: QEvent, /) -> bool:
        if event.type() == event.Type.WindowDeactivate:
            logger.debug("deactivate event")
            self._despawn()
        return super().event(event)

    @override
    def resizeEvent(self, event: QResizeEvent, /) -> None:
        super().resizeEvent(event)
        self._corner_mask.resize(event.size())

    @override
    def paintEvent(self, event: QPaintEvent, /) -> None:
        _color = theme.main_window.background_color.value
        color = self.palette().window() if _color is None else QColor(_color)
        with QPainter(self) as p:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawRect(self.rect())
