"""Data objects shared by the network module and everything that uses it.

Kept apart from the Qt client so that consumers and their UI widgets can import the progress and
error shapes without pulling in ``PySide6.QtNetwork``.

Currently defines:
    - NetworkError: a request that was refused, failed or cancelled.
    - Downloaded: progress of a single file download.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NetworkError:
    """Describes a request that did not yield a usable response.

    Handed to callbacks and emitted on signals rather than raised, because reaching the network is
    best effort: the application runs in offline mode, hosts go down and users cancel. Callers are
    meant to render this instead of crashing on it.
    """

    error_str: str = "Failed to reach the server."
    url: str = ""
    "The requested url. Empty when the url itself was the problem."
    status: int | None = None
    "HTTP status code when the request reached the server, otherwise None."
    aborted: bool = False
    "The request was cancelled locally, so no server response is expected."


@dataclass(frozen=True)
class Downloaded:
    """Progress of a single file download.

    The field order matches the ``updater.Downloaded`` this module generalizes, so the existing
    positional construction in the updater keeps working.
    """

    download_progress: float
    "Fraction of the transfer finished, from 0.0 to 1.0."
    downloaded_size: int
    "Bytes received so far."
    total_size: int
    "Bytes expected in total. 0 when the server sends no Content-Length."
    completed: bool
    "The whole file was written, so file_path is only meaningful when True."
    file_path: Path
    speed: float | None = None
    "Average bytes per second since the transfer began. None if not measurable."
    aborted: bool = False
    "The transfer stopped before completing: cancelled, refused or failed."
    url: str = ""
