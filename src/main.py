import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from providers._base_provider import BaseProvider
    from providers._base_result import BaseResult


class CLIRenderer:
    def __init__(self) -> None:
        self.last_line_len: int = 0

    def print(self, msg: str) -> None:
        self.print_lines(msg.splitlines())

    def print_lines(self, lines: list[str]) -> None:
        print(
            "\r\033[K"
            + "\033[F\033[K" * (self.last_line_len - 1)
            + "\n" * (self.last_line_len - len(lines))
            + str("\n".join(lines)),
            end="",
        )
        self.last_line_len = max(len(lines), self.last_line_len)


def cli() -> None:
    import msvcrt
    import string

    from providers import PROVIDERS
    from providers._base_result import ExecutionActions

    # Prepare providers
    providers: list[BaseProvider] = []
    for provider in PROVIDERS:
        providers.append(provider())

    renderer = CLIRenderer()

    print()
    renderer.print("Query: ")
    query_buffer = ""
    first_res: BaseResult | None = None
    while True:
        ch = msvcrt.getwch()
        match ch:
            case "\x03":
                break
            case "\r":
                if first_res is not None:
                    first_res.execute(ExecutionActions.Enter)
                continue
            case "\x08":
                query_buffer = query_buffer[:-1]
            case _:
                if ch in string.ascii_letters + string.digits + string.punctuation + " ":
                    query_buffer += ch

        # get results
        results: list[BaseResult] = []
        for provider in providers:
            results.extend(provider.search(query_buffer))

        first_res = results[0] if results else None

        # prepare results
        p_lines: list[str] = []
        for result in results:
            p_lines.append(f"{result.highlighted('\033[32m', '\033[0m')}")

        p_lines.append(f"Query: {query_buffer}")
        renderer.print_lines(p_lines)


def ui() -> None:
    from collections.abc import Callable

    import keyboard
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

    from ui import MainWindow

    class HotkeyHandler(QObject):
        trigger: Signal = Signal()

        def __init__(
            self,
            callback: Callable[[], None],
            /,
            parent: QObject | None = None,
            *,
            objectName: str | None = None,
        ) -> None:
            super().__init__(parent, objectName=objectName)

            _ = self.trigger.connect(callback)
            _ = keyboard.add_hotkey("alt+space", self._on_trigger, suppress=True)

        def _on_trigger(self) -> None:
            self.trigger.emit()
            keyboard.release("alt")
            keyboard.release("left alt")
            keyboard.release("right alt")

    app = QApplication(sys.argv)
    tray = QSystemTrayIcon()
    tray.setContextMenu(menu := QMenu("Quit"))
    menu.addAction(act := QAction("Quit"))
    _ = act.triggered.connect(app.quit)
    tray.show()
    window = MainWindow()
    window.show()

    _ = HotkeyHandler(window.show)

    _ = app.exec()


def main() -> None:
    import logging

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )

    if "cli" in sys.argv:
        cli()
    else:
        ui()


if __name__ == "__main__":
    main()
