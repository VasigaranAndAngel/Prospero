import atexit
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from providers import BaseResult
    from providers._base_provider import BaseProvider


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

    from providers import PROVIDERS, ExecutionAction

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
                    first_res.execute(ExecutionAction.Enter)
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

        results.sort(key=lambda x: x.score)  # sorted upside down

        first_res = results[-1] if results else None

        # prepare results
        p_lines: list[str] = []
        for result in results:
            p_lines.append(f"{result.highlighted('\033[32m', '\033[0m')}")

        p_lines.append(f"Query: {query_buffer}")
        renderer.print_lines(p_lines)


def ui() -> None:
    from PySide6.QtGui import QAction, QIcon
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

    import assets
    import constants
    from hotkey_listener import HotkeyListener
    from ui import MainWindow
    from updater import Updater

    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    tray = QSystemTrayIcon(
        QIcon(assets.APP_ICON_PNG.as_posix()), window, toolTip=constants.APPLICATION_NAME.title()
    )

    def _on_ac(reason: QSystemTrayIcon.ActivationReason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            window.show()

    _ = tray.activated.connect(_on_ac)
    tray.setContextMenu(menu := QMenu("Quit"))
    menu.addAction(act := QAction("Quit"))
    _ = act.triggered.connect(app.quit)
    tray.show()

    hk_listener = HotkeyListener()
    _ = hk_listener.trigger.connect(window.show)
    _ = atexit.register(hk_listener.stop)
    hk_listener.start()

    # Set parent of Updater to window
    u = Updater()
    u.setParent(window)

    _ = app.exec()


def main() -> None:
    import logging

    from constants import SCHTASKS_HANDLER_MODE

    _ = SCHTASKS_HANDLER_MODE

    arg = "--schtasks-handler"
    if arg in sys.argv:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s:%(levelname)s:%(name)s - %(message)s",
            stream=open("schtasks-handler.log", "a"),
        )
        logger = logging.getLogger(__name__)

        if len(sys.argv) > (idx := sys.argv.index(arg)) + 2:
            SCHTASKS_HANDLER_MODE = True  # pyright: ignore[reportConstantRedefinition]
            try:
                from helpers import task_schedule_handler

                logger.debug("Starting listener...")
                _ = task_schedule_handler.start_listener(*sys.argv[idx + 1 : idx + 3])
            except Exception as e:
                logger.error(f"Error running TaskScheduleHandler: {e}")
        else:
            logger.error(
                f"Authkey and port arguments are missing. NOTE: '{arg}' argument is only for internal uses."
            )

    else:
        from constants import APPLICATION_NAME as AN

        stream = open(f"{AN.title()}.log", "a") if getattr(sys, "frozen", False) else sys.stdout
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s:%(levelname)s:%(name)s - %(message)s",
            stream=stream,
        )

        if "cli" in sys.argv:
            cli()
        else:
            ui()


if __name__ == "__main__":
    main()
