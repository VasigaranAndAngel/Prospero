from pynput import keyboard
from pynput.keyboard import Key, KeyCode
from PySide6.QtCore import QObject, Signal

from platform_utils import IS_WINDOWS

VK_CODE_SPACE = 32

_ALT_KEYS = {Key.alt, Key.alt_l, Key.alt_r, Key.alt_gr}


class HotkeyListener(QObject):
    """Global ``Alt + Space`` listener.

    On Windows a low level event filter is used so the key can be swallowed before the
    focused application sees it. Other platforms use the plain listener: pynput does not
    support suppressing events on X11, so the key still reaches the focused window.
    """

    trigger: Signal = Signal()

    def __init__(self, /, parent: QObject | None = None, *, objectName: str | None = None) -> None:
        super().__init__(parent, objectName=objectName)
        self._alt_pressed: bool = False

        listener_kwargs: dict[str, object] = {}
        if IS_WINDOWS:
            listener_kwargs["win32_event_filter"] = self._win32_event_filter

        self._listener: keyboard.Listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            **listener_kwargs,  # pyright: ignore[reportArgumentType]
        )

    def _on_press(self, key: Key | KeyCode | None) -> None:
        if IS_WINDOWS:
            self._alt_pressed = key == Key.alt_l
            return

        if key in _ALT_KEYS:
            self._alt_pressed = True
        elif self._alt_pressed and key == Key.space:
            self.trigger.emit()

    def _win32_event_filter(self, msg, data):  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType, reportUnusedParameter]
        if data.vkCode == VK_CODE_SPACE and self._alt_pressed:  # pyright: ignore[reportUnknownMemberType]
            self.trigger.emit()
            self._listener.suppress_event()  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

    def _on_release(self, key: Key | KeyCode | None) -> None:
        if key in _ALT_KEYS:
            self._alt_pressed = False

    def start(self) -> None:
        self._listener.start()

    def stop(self) -> None:
        self._listener.stop()
