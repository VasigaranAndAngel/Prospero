import sys

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

# region Github repository details
REPO_OWNER = "VasigaranAndAngel"
REPO_NAME = "Prospero"
# endregion

__all__ = ["APPLICATION_NAME", "APPLICATION_VERSION", "VERSION", "REPO_OWNER", "REPO_NAME"]
