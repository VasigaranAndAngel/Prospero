"""
## AnimatedVBoxLayout

A QLayout subclass that behaves like a QVBoxLayout but animates widgets into their new positions
when the arrangement changes (adds, removes, and reorders).

NOTE: Need to test for memory leaks.
"""

from collections.abc import Callable, Sequence
from typing import Literal, override

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QWidget, QWidgetItem


class AnimatedVBoxLayout(QLayout):
    def __init__(
        self,
        parent: QWidget | None = None,
        duration: int = 500,
        easing: QEasingCurve.Type | QEasingCurve = QEasingCurve.Type.Linear,
    ):
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        "Contains layout items in current order"
        self._anims: dict[QWidget, QPropertyAnimation] = {}
        "QPropertyAnimation instances mapped to widgets."
        self._target_rects: dict[QWidget, QRect] = {}
        "Target QRects of mapped widget."
        self._new_widgets: set[QWidget] = set()
        "Widgets that haven't been placed yet."
        self._force_anim_restart: set[QWidget] = set()
        "Widgets that should be animated forcefully on next self._relayout()."
        self._duration: int = duration
        self._easing: QEasingCurve = QEasingCurve(easing)

    # region QLayout plumbing
    @override
    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)
        self.invalidate()

    @override
    def count(self) -> int:
        return len(self._items)

    @override
    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    @override
    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    @override
    def expandingDirections(self) -> Literal[Qt.Orientation.Vertical]:
        return Qt.Orientation.Vertical

    @override
    def hasHeightForWidth(self) -> Literal[False]:
        return False

    @override
    def sizeHint(self) -> QSize:
        return self._compute_size(lambda i: i.sizeHint())

    @override
    def minimumSize(self) -> QSize:
        return self._compute_size(lambda i: i.minimumSize())

    def _compute_size(self, getter: Callable[[QLayoutItem], QSize]):
        w = 0
        h = 0
        for item in self._items:
            s = getter(item)
            w = max(w, s.width())
            h += s.height()
        if self._items:
            h += self.spacing() * (len(self._items) - 1)
        m = self.contentsMargins()
        w += m.left() + m.right()
        h += m.top() + m.bottom()
        return QSize(w, h)

    # endregion

    # region public API
    @override
    def addWidget(self, widget: QWidget):
        self.insertWidget(len(self._items), widget)

    def insertWidget(self, index: int, widget: QWidget):
        item = QWidgetItem(widget)
        self._items.insert(index, item)
        widget.setParent(self.parentWidget())
        self._new_widgets.add(widget)
        widget.show()  # this will trigger self._relayout()
        self.invalidate()
        # self._relayout()

    @override
    def removeWidget(self, widget: QWidget):
        for i, item in enumerate(self._items):
            if item.widget() is widget:
                _ = self._items.pop(i)
                break
        self._cleanup_widget(widget)
        widget.hide()
        widget.setParent(None)
        self.invalidate()
        self._relayout()

    def moveWidget(self, from_index: int, to_index: int):
        item = self._items.pop(from_index)
        self._items.insert(to_index, item)
        wid = item.widget()
        if wid is not None:
            self._force_anim_restart.add(wid)
        self.invalidate()
        self._relayout()

    def setWidgets(self, widgets: Sequence[QWidget]):
        """Reconcile current contents to exactly `widgets` (in this order), animating
        adds/removes/moves in one pass."""
        old_widgets = [it.widget() for it in self._items]
        new_set = set(widgets)

        for w in old_widgets:
            if w not in new_set and w is not None:
                self.removeWidget(w)

        current = {it.widget(): it for it in self._items}
        new_items: list[QLayoutItem] = []
        for w in widgets:
            if w in current:
                new_items.append(current[w])
                self._force_anim_restart.add(w)
            else:
                w.setParent(self.parentWidget())
                self._new_widgets.add(w)
                w.show()
                new_items.append(QWidgetItem(w))
        self._items = new_items
        self.invalidate()
        self._relayout()

    # endregion

    # region geometry engine
    @override
    def setGeometry(self, rect: QRect):
        super().setGeometry(rect)
        self._relayout(rect)

    def _relayout(self, rect: QRect | None = None):
        if rect is None:
            rect = self.geometry()
        if not rect.isValid():
            return

        r = self.contentsRect()
        x = r.x()
        y = r.y()
        w = r.width()

        seen: set[QWidget] = set()
        for item in self._items:
            widget = item.widget()
            if widget is None:
                continue
            hint_h = item.sizeHint().height()
            min_h = item.minimumSize().height()
            h = max(hint_h, min_h)
            target = QRect(x, y, w, h)
            seen.add(widget)
            self._apply_target(widget, target)
            y += h + self.spacing()

    def _apply_target(self, widget: QWidget, target: QRect):
        prev_target = self._target_rects.get(widget)
        if prev_target == target:
            return  # nothing actually changed for this widget. leave it alone

        self._target_rects[widget] = target

        if widget in self._new_widgets:
            self._new_widgets.discard(widget)
            widget.setGeometry(target)  # place instantly, no animation
            return

        anim = self._anims.get(widget)
        force = widget in self._force_anim_restart
        if not force and anim is not None and anim.state() == QPropertyAnimation.State.Running:
            # already moving: re-target smoothly, should not restart
            anim.setEndValue(target)
            return

        self._force_anim_restart.discard(widget)

        if anim is None:
            anim = QPropertyAnimation(widget, b"geometry", self)
        anim.stop()
        anim.setDuration(self._duration)
        anim.setEasingCurve(self._easing)
        anim.setStartValue(widget.geometry())
        anim.setEndValue(target)
        self._anims[widget] = anim
        anim.start()

    def _cleanup_widget(self, widget: QWidget) -> None:
        # NOTE: will be removed from self._items in removeWidget()
        anim = self._anims.pop(widget, None)
        if anim is not None:
            anim.stop()
            anim.setParent(None)
            anim.deleteLater()
        _ = self._target_rects.pop(widget, None)
        self._new_widgets.discard(widget)
        self._force_anim_restart.discard(widget)

    # endregion
