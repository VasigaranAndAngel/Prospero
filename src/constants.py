# NOTE: Avoid importing too much because this will be imported on --schtasks-handler mode.
import ctypes
import os
import sys
from pathlib import Path

from packaging.version import Version

APPLICATION_NAME = "prospero"
"Name of the application"


def _get_version_from_metadata() -> str:
    from importlib import metadata

    try:
        return metadata.version("prospero")
    except metadata.PackageNotFoundError:
        return "0.0.0"


if getattr(sys, "frozen", False):
    try:
        from ._version import __version__
    except ImportError:
        __version__ = _get_version_from_metadata()
else:
    __version__ = _get_version_from_metadata()

APPLICATION_VERSION: Version = Version(__version__)
"Version of the application"
VERSION: Version = APPLICATION_VERSION
"Version of the application"
APPLICATION_PATH = Path(sys.executable)
"Path of the .exe file if frozen, otherwise path of python.exe"

# region Github repository details
REPO_OWNER = "VasigaranAndAngel"
REPO_NAME = "Prospero"
# endregion

try:
    _as_admin = os.getuid() == 0
except AttributeError:
    _as_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0  # pyright: ignore[reportAny]
RUNNING_AS_ADMIN: bool = _as_admin
SCHTASKS_HANDLER_MODE: bool = False

__all__ = [
    "APPLICATION_NAME",
    "APPLICATION_VERSION",
    "VERSION",
    "REPO_OWNER",
    "REPO_NAME",
    "RUNNING_AS_ADMIN",
]
