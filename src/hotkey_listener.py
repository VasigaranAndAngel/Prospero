from pynput import keyboard
from pynput.keyboard import Key, KeyCode
from PySide6.QtCore import QObject, Signal

VK_CODE_SPACE = 32


class HotkeyListener(QObject):
    trigger: Signal = Signal()

    def __init__(self, /, parent: QObject | None = None, *, objectName: str | None = None) -> None:
        super().__init__(parent, objectName=objectName)
        self._alt_pressed: bool = False
        self._listener: keyboard.Listener = keyboard.Listener(
            on_press=self._on_press,
            win32_event_filter=self._win32_event_filter,  # pyright: ignore[reportUnknownMemberType]
            on_release=self._on_release,
        )

    def _on_press(self, key: Key | KeyCode | None) -> None:
        self._alt_pressed = key == Key.alt_l

    def _win32_event_filter(self, msg, data):  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType, reportUnusedParameter]
        if data.vkCode == VK_CODE_SPACE and self._alt_pressed:  # pyright: ignore[reportUnknownMemberType]
            self.trigger.emit()
            self._listener.suppress_event()  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

    def _on_release(self, key: Key | KeyCode | None) -> None:
        if key == Key.alt_l:
            self._alt_pressed = False

    def start(self) -> None:
        self._listener.start()

    def stop(self) -> None:
        self._listener.stop()
