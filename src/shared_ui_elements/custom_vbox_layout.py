from typing import override

from PySide6.QtCore import (
    QAnimationGroup,
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
)
from PySide6.QtWidgets import QVBoxLayout, QWidget


class CustomVBoxLayout(QVBoxLayout):
    animate: bool = True
    newly_added_widgets: list[QWidget] = []
    duration: int = 200
    easing_curve: QEasingCurve | QEasingCurve.Type = QEasingCurve.Type.OutExpo

    def __init__(self, parent: QWidget | None = None) -> None:
        if parent is None:
            super().__init__()
        else:
            super().__init__(parent)

        self._animation_group: QAnimationGroup = QParallelAnimationGroup(self)

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
        self._animation_group.stop()
        # self._group.clear()
        while self._animation_group.animationCount():
            anim = self._animation_group.animationAt(0)
            self._animation_group.removeAnimation(anim)
            anim.deleteLater()

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
            self._animation_group.addAnimation(anim)
            any_moving = True

        if any_moving:
            self._animation_group.start()
