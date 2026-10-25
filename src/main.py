import atexit
import sys
from typing import TYPE_CHECKING

import constants  # for update APP_STARTED_TIME  # noqa: F401
from platform_specific import require_supported
from platform_specific.cli import read_key
from platform_specific.display import configure_qt_platform

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
    import string

    from providers import PROVIDERS_I, ExecutionAction

    # Reuse the provider instances created on import. Building new ones would register the
    # placeholder tokens a second time and raise.
    providers: list[BaseProvider] = list(PROVIDERS_I)

    renderer = CLIRenderer()

    print()
    renderer.print("Query: ")
    query_buffer = ""
    first_res: BaseResult | None = None
    while True:
        ch = read_key()
        match ch:
            case "\x03":
                break
            case "\r":
                if first_res is not None:
                    first_res.execute(ExecutionAction.Trigger)
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
    from platform_specific.hotkeys import HotkeyListener
    from ui import MainWindow
    from updater import Updater

    configure_qt_platform()

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
    require_supported()

    import logging

    from arg_parser import args

    schtasks_handler = args.schtasks_handler
    if schtasks_handler is not None:
        stream = open("schtasks-handler.log", "a")
        _ = atexit.register(stream.close)
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s:%(levelname)s:%(name)s - %(message)s",
            stream=stream,
        )
        logger = logging.getLogger(__name__)

        try:
            from platform_specific.startup import start_listener

            logger.debug("Starting listener...")
            _ = start_listener(schtasks_handler[0], schtasks_handler[1])
        except Exception as e:
            logger.error(f"Error running TaskScheduleHandler: {e}")

    else:
        from constants import APPLICATION_NAME as AN

        if getattr(sys, "frozen", False):
            stream = open(f"{AN.title()}.log", "a")
            _ = atexit.register(stream.close)
        else:
            stream = sys.stdout

        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s:%(levelname)s:%(name)s - %(message)s",
            stream=stream,
        )

        if args.cli:
            cli()
        else:
            ui()


if __name__ == "__main__":
    main()
