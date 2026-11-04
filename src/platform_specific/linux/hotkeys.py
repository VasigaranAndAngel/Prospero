"""Linux global hotkey listener.

pynput cannot suppress events on X11, so the hotkey also reaches the focused window.
"""

from __future__ import annotations

from pynput import keyboard
from pynput.keyboard import Key, KeyCode
from PySide6.QtCore import QObject, Signal

_ALT_KEYS = {Key.alt, Key.alt_l, Key.alt_r, Key.alt_gr}


class HotkeyListener(QObject):
    """Global ``Alt + Space`` listener."""

    trigger: Signal = Signal()

    def __init__(
        self, /, parent: QObject | None = None, *, objectName: str | None = None
    ) -> None:
        super().__init__(parent, objectName=objectName)
        self._alt_pressed: bool = False
        self._listener: keyboard.Listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )

    def _on_press(self, key: Key | KeyCode | None) -> None:
        if key in _ALT_KEYS:
            self._alt_pressed = True
        elif self._alt_pressed and key == Key.space:
            self.trigger.emit()

    def _on_release(self, key: Key | KeyCode | None) -> None:
        if key in _ALT_KEYS:
            self._alt_pressed = False

    def start(self) -> None:
        self._listener.start()

    def stop(self) -> None:
        self._listener.stop()


__all__ = ["HotkeyListener"]
