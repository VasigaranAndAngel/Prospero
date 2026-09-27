"""Single entry point for every internet request the project makes.

Use :class:`NetworkClient` rather than ``QNetworkAccessManager`` directly, so that connection
sharing, the offline check, headers, timeouts, redirects and download streaming are handled
consistently. See the module docstring in ``_client.py`` for the details.

Currently defines:
    - NetworkClient: the shared client.
    - NetworkError: a request that was refused, failed or cancelled.
    - Downloaded: progress of a single file download.
"""

from ._client import DEFAULT_TIMEOUT_MS, OFFLINE_ERROR, USER_AGENT, NetworkClient
from ._dataclasses import Downloaded, NetworkError

__all__ = [
    "DEFAULT_TIMEOUT_MS",
    "OFFLINE_ERROR",
    "USER_AGENT",
    "Downloaded",
    "NetworkClient",
    "NetworkError",
]
