import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from constants import APPLICATION_NAME, VERSION

if TYPE_CHECKING:

    class ArgParserNamespace(Protocol):
        "Represents parsed arguments' Namespace. Implemented only for type checking."

        cli: bool
        debug: bool
        offline: bool
        schtasks_handler: list[str] | None
        config: list[Path] | None
        theme: list[Path] | None
        dark_theme: list[Path] | None
        light_theme: list[Path] | None
        update_domain: list[str] | None


_parser = argparse.ArgumentParser(prog=APPLICATION_NAME.title())

_ = _parser.add_argument("-v", "--version", action="version", version=str(VERSION))
_ = _parser.add_argument("-c", "--config", type=Path, nargs=1, help="Set config file.")
_ = _parser.add_argument("-d", "--debug", action="store_true", help="Set log level to debug.")
_ = _parser.add_argument("--cli", action="store_true", help="Start in cli mode.")
_ = _parser.add_argument("--theme", type=Path, nargs=1, help="Theme file for both dark and light.")
_ = _parser.add_argument("--dark-theme", type=Path, nargs=1, help="Set dark theme file.")
_ = _parser.add_argument("--light-theme", type=Path, nargs=1, help="Set light theme file.")
_ = _parser.add_argument("--offline", action="store_true", help="Never connects to internet.")
_ = _parser.add_argument("--update-domain", nargs=1, type=str, help="Set domain to fetch update.")
_ = _parser.add_argument("--schtasks-handler", nargs=2, type=str, help=argparse.SUPPRESS)

args, leftovers = cast("tuple[ArgParserNamespace, list[str]]", _parser.parse_known_args())

del _
del _parser

__all__ = ["args", "leftovers"]

# TODO: Add help for cli args for configs and themes too.
