"""The single place this project talks to the internet.

Every outbound request is expected to go through :class:`NetworkClient` so that cross cutting
concerns stay in one place instead of being reimplemented per caller:

- a single shared ``QNetworkAccessManager``, so connections are pooled and there is one Qt network
  object to own rather than one per feature.
- the ``--offline`` check, consulted at request time rather than import time.
- a ``User-Agent`` on every request. Qt does not send one by default and the GitHub API answers
  requests without it with 403.
- a timeout and a redirect policy that refuses to downgrade https.
- streaming downloads, so a large file is never held in memory in full.

Two request styles are offered:

- :meth:`NetworkClient.fetch` for small payloads, delivering ``bytes``.
- :meth:`NetworkClient.download` for files, delivering progress and writing the
  file to disk itself.

Both accept an optional callback and also emit signals, and both can be cancelled through
:meth:`NetworkClient.cancel`.
"""

import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO, ClassVar, Final, Self
from urllib.parse import urljoin

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from arg_parser import args
from constants import APPLICATION_NAME, APPLICATION_VERSION, REPO_NAME, REPO_OWNER
from helpers import SingletonQObjectMeta

from ._dataclasses import Downloaded, NetworkError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_MS: Final[int] = 30_000
"Applies to every request unless the caller passes another value."

OFFLINE_ERROR: Final[str] = "Application running in offline mode. Can't connect to internet."

USER_AGENT: Final[str] = (
    f"{APPLICATION_NAME.title()}/{APPLICATION_VERSION} (+https://github.com/{REPO_OWNER}/{REPO_NAME})"
)
"Sent on every request. GitHub rejects requests that carry no User-Agent."


@dataclass
class _Transfer:
    """Mutable state of one in flight request. Not exposed outside this module."""

    reply: QNetworkReply
    url: str
    started_at: float = 0.0
    received: int = 0
    total: int = 0
    handle: IO[bytes] | None = None
    tmp_path: Path | None = None
    file_path: Path = Path()
    "Where a finished download is expected. Unused by plain fetches."
    finished: bool = False
    "Guards against finishing twice, since abort and finished can both fire."


class NetworkClient(QObject, metaclass=SingletonQObjectMeta):
    """Shared client for every internet request the project makes.

    Inherits ``QObject``, so the first instantiation must happen after a
    ``QApplication`` exists. Being a singleton, that first call is what creates
    the underlying ``QNetworkAccessManager``.
    """

    fetch_started: Signal = Signal(str)
    "Emitted with the url when a fetch begins."
    fetched: Signal = Signal(str, object)
    "Emitted with the url and either the payload bytes or a NetworkError."
    download_started: Signal = Signal(str)
    "Emitted with the url when a download begins."
    downloaded: Signal = Signal(Downloaded)
    "Emitted while a download runs and once when it ends."

    _base_urls: ClassVar[dict[str, str]] = {}
    "Service name to base url overrides, for mirrors and proxies."

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._manager: QNetworkAccessManager = QNetworkAccessManager(self)
        self._transfers: dict[str, _Transfer] = {}
        "In flight requests, keyed by url."

    @classmethod
    def user_agent(cls) -> str:
        return USER_AGENT

    @property
    def offline(self) -> bool:
        """Whether the application was started with ``--offline``."""
        return args.offline

    @classmethod
    def set_base_url(cls, service: str, base_url: str | None) -> None:
        """Overrides the base url of a service, or clears the override with None.

        Args:
            service (str): Logical service name, e.g. ``"github"``.
            base_url (str | None): Base url to use, e.g. a mirror or proxy.
        """
        if base_url is None:
            _ = cls._base_urls.pop(service, None)
        else:
            cls._base_urls[service] = base_url.rstrip("/")

    @classmethod
    def resolve(cls, service: str, default_base: str, path: str = "") -> str:
        """Builds a url for a service, honouring any base url override.

        Args:
            service (str): Logical service name, e.g. ``"github"``.
            default_base (str): Base url to use when no override is set.
            path (str): Path to append, relative to the base url.

        Returns:
            str: The absolute url.
        """
        base = cls._base_urls.get(service, default_base).rstrip("/")
        return urljoin(f"{base}/", path) if path else base

    def active(self) -> list[str]:
        """Urls of the requests currently in flight."""
        return list(self._transfers)

    def cancel(self, url: str) -> None:
        """Cancels the in flight request for the given url, if any.

        Args:
            url (str): The url of the request to cancel.
        """
        if (transfer := self._transfers.get(url)) is not None:
            logger.debug("Cancelling request: %s", url)
            _ = transfer.reply.abort()

    def cancel_all(self) -> None:
        """Cancels every in flight request."""
        for url in self.active():
            self.cancel(url)

    def fetch(
        self,
        url: str | QUrl,
        callback: Callable[[bytes | NetworkError], None] | None = None,
        /,
        *,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        """Fetches a small payload into memory.

        Args:
            url (str | QUrl): What to fetch.
            callback (Callable | None): Called with the payload bytes, or a
                NetworkError if it did not arrive.
            timeout_ms (int): Milliseconds before the request is given up on.
        """
        uri = url.toString() if isinstance(url, QUrl) else url

        if self.offline:
            logger.warning("Refusing to fetch %s. %s", uri, OFFLINE_ERROR)
            _ = self._deliver(uri, NetworkError(OFFLINE_ERROR, uri), callback)
            return

        reply = self._manager.get(self._build_request(uri, timeout_ms))
        self._transfers[uri] = _Transfer(reply=reply, url=uri, started_at=time.time())
        self.fetch_started.emit(uri)
        logger.debug("Fetching %s", uri)

        def _on_finished() -> None:
            error = self._reply_error(reply, uri)
            payload = bytes(reply.readAll().data()) if error is None else None
            _ = self._transfers.pop(uri, None)
            _ = self._deliver(uri, error if error is not None else bytes(payload or b""), callback)

        _ = reply.finished.connect(_on_finished)

    def download(
        self,
        url: str | QUrl,
        file_path: Path,
        callback: Callable[[Downloaded], None] | None = None,
        /,
        *,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        """Downloads a file to disk, streaming it as it arrives.

        The file is written to a ``.part`` sibling first and moved into place
        only once the transfer completes, so a half written file is never left
        where a complete one is expected.

        Args:
            url (str | QUrl): What to download.
            file_path (Path): Where to put the finished file.
            callback (Callable | None): Called with progress as it changes.
            timeout_ms (int): Milliseconds before the request is given up on.
        """
        uri = url.toString() if isinstance(url, QUrl) else url

        if self.offline:
            logger.warning("Refusing to download %s. %s", uri, OFFLINE_ERROR)
            _ = self._emit_downloaded(
                Downloaded(0, 0, 0, False, file_path, aborted=True, url=uri), callback
            )
            return

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = file_path.with_name(f"{file_path.name}.part")
            handle: IO[bytes] = tmp_path.open("wb")
        except OSError as e:
            logger.warning("Cannot write download of %s to %s: %s", uri, file_path, e)
            _ = self._emit_downloaded(
                Downloaded(0, 0, 0, False, file_path, aborted=True, url=uri), callback
            )
            return

        reply = self._manager.get(self._build_request(uri, timeout_ms))
        transfer = _Transfer(
            reply=reply,
            url=uri,
            started_at=time.time(),
            handle=handle,
            tmp_path=tmp_path,
            file_path=file_path,
        )
        self._transfers[uri] = transfer
        self.download_started.emit(uri)
        logger.debug("Downloading %s to %s", uri, file_path)

        def _on_ready() -> None:
            chunk = bytes(reply.readAll().data())
            transfer.received += len(chunk)
            if transfer.handle is not None:
                _ = transfer.handle.write(chunk)

        def _on_progress(received: int, total: int) -> None:
            transfer.received = received
            transfer.total = total
            self._emit_progress(transfer, callback)

        def _on_finished() -> None:
            if transfer.finished:
                return
            transfer.finished = True
            _ = self._transfers.pop(uri, None)

            error = self._reply_error(reply, uri)
            _ = self._close_handle(transfer)

            if error is None:
                try:
                    _ = os.replace(tmp_path, file_path)
                except OSError as e:
                    _ = self._remove_partial(transfer)
                    logger.warning("Failed to store download of %s as %s: %s", uri, file_path, e)
                    _ = self._emit_downloaded(
                        Downloaded(
                            0,
                            transfer.received,
                            transfer.total,
                            False,
                            file_path,
                            aborted=True,
                            url=uri,
                        ),
                        callback,
                    )
                    return
                logger.debug("Downloaded %s to %s", uri, file_path)
                _ = self._emit_downloaded(
                    Downloaded(
                        1.0,
                        transfer.received,
                        transfer.received,
                        True,
                        file_path,
                        self._speed(transfer),
                        url=uri,
                    ),
                    callback,
                )
            else:
                _ = self._remove_partial(transfer)
                logger.warning("Download of %s did not finish: %s", uri, error.error_str)
                _ = self._emit_downloaded(
                    Downloaded(
                        0,
                        transfer.received,
                        transfer.total,
                        False,
                        file_path,
                        aborted=True,
                        url=uri,
                    ),
                    callback,
                )

        _ = reply.readyRead.connect(_on_ready)
        _ = reply.downloadProgress.connect(_on_progress)
        _ = reply.finished.connect(_on_finished)

    def _build_request(self, url: str, timeout_ms: int) -> QNetworkRequest:
        request = QNetworkRequest(QUrl(url))
        _ = request.setRawHeader(b"User-Agent", USER_AGENT.encode("ascii", "replace"))
        _ = request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )
        request.setTransferTimeout(timeout_ms)
        return request

    def _reply_error(self, reply: QNetworkReply, url: str) -> NetworkError | None:
        """Turns a reply's error state into a NetworkError, or None if it succeeded."""
        if (code := reply.error()) == QNetworkReply.NetworkError.NoError:
            return None

        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)  # pyright: ignore[reportAny]
        detail = reply.errorString() or "Unknown network error."
        if status:
            detail = f"HTTP {status}: {detail}"

        return NetworkError(
            error_str=detail,
            url=url,
            status=int(status) if status else None,  # pyright: ignore[reportAny]
            aborted=code is QNetworkReply.NetworkError.OperationCanceledError,
        )

    def _deliver(
        self,
        url: str,
        result: bytes | NetworkError,
        callback: Callable[[bytes | NetworkError], None] | None,
    ) -> Self:
        _ = self.fetched.emit(url, result)
        if callback is not None:
            callback(result)
        return self

    def _emit_progress(
        self, transfer: _Transfer, callback: Callable[[Downloaded], None] | None
    ) -> None:
        total = transfer.total
        if total > 0:
            _ = self._emit_downloaded(
                Downloaded(
                    min(transfer.received / total, 1.0),
                    transfer.received,
                    total,
                    False,
                    transfer.file_path,
                    self._speed(transfer),
                    url=transfer.url,
                ),
                callback,
            )

    def _emit_downloaded(
        self, state: Downloaded, callback: Callable[[Downloaded], None] | None
    ) -> Self:
        self.downloaded.emit(state)
        if callback is not None:
            callback(state)
        return self

    def _speed(self, transfer: _Transfer) -> float | None:
        elapsed = time.time() - transfer.started_at
        return transfer.received / elapsed if elapsed > 0 else None

    def _close_handle(self, transfer: _Transfer) -> bool:
        """Closes the temporary file so its contents are flushed. Returns True on success."""
        if transfer.handle is None:
            return True
        try:
            transfer.handle.close()
        except OSError as e:
            logger.warning("Failed to close partial download %s: %s", transfer.tmp_path, e)
            return False
        finally:
            transfer.handle = None
        return True

    def _remove_partial(self, transfer: _Transfer) -> bool:
        """Deletes the temporary file of a download that will not be completed."""
        if transfer.tmp_path is None or not transfer.tmp_path.exists():
            return True
        try:
            transfer.tmp_path.unlink()
        except OSError as e:
            logger.warning("Failed to remove partial download %s: %s", transfer.tmp_path, e)
            return False
        return True
