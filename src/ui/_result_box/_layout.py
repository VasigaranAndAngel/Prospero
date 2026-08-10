from typing import override

from PySide6.QtCore import (
    QAbstractAnimation,
    QAnimationGroup,
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
)
from PySide6.QtWidgets import QVBoxLayout, QWidget


class CustomVBoxLayout(QVBoxLayout):
    _group: QAnimationGroup | None = None
    animate: bool = True
    newly_added_widgets: list[QWidget] = []
    duration: int = 200
    easing_curve: QEasingCurve | QEasingCurve.Type = QEasingCurve.Type.OutExpo

    @override
    def setGeometry(self, arg__1: QRect, /) -> None:
        if not self.animate:
            return super().setGeometry(arg__1)

        # capture where each child widget currently is
        before: dict[QWidget, QRect] = {}
        for i in range(self.count()):
            item = self.itemAt(i)
            widget = item.widget() if item is not None else None
            if widget is not None:
                before[widget] = widget.geometry()

        # let Qt compute layout
        super().setGeometry(arg__1)

        # capture the targets, then snap back to "before" so we can animate
        targets: dict[QWidget, QRect] = {}
        for widget, start in before.items():
            targets[widget] = widget.geometry()
            if widget in self.newly_added_widgets and start.isValid():
                widget.setGeometry(start)

        # stop/replace any animation already running.
        if self._group is not None:
            try:
                self._group.stop()
            except RuntimeError:
                pass
            self._group = None

        group = QParallelAnimationGroup(self)
        any_moving = False
        for widget, target in targets.items():
            if widget in self.newly_added_widgets:
                self.newly_added_widgets.remove(widget)
                widget.setGeometry(target)
                continue
            start = before[widget]
            if not start.isValid() or start == target:
                widget.setGeometry(target)
                continue
            anim = QPropertyAnimation(widget, b"geometry", widget)
            anim.setDuration(self.duration)
            anim.setEasingCurve(self.easing_curve)
            anim.setStartValue(start)
            anim.setEndValue(target)
            group.addAnimation(anim)
            any_moving = True

        if any_moving:
            self._group = group
            group.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        else:
            self._group = None
