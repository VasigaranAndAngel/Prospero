"""Shared fixtures for tests that need Qt and a real socket.

The network tests talk to a throwaway HTTP server bound to 127.0.0.1 rather than a stubbed
``QNetworkReply``, because the behavior worth pinning down lives in Qt: streaming, headers, progress
and abort semantics.
"""

import os
import time
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import cast, override
from urllib.parse import urlsplit

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop

from arg_parser import args
from helpers.singleton_meta import SingletonMeta
from network import NetworkClient

_ = os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_ = os.environ.setdefault("no_proxy", "127.0.0.1,localhost")
_ = os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")

PAYLOAD: bytes = b'{"ok": true}'
FILE_SIZE: int = 512 * 1024
"Size served by /file, big enough to arrive in several chunks."

PUMP_TIMEOUT_S: float = 20.0
"How long a test will spin the event loop before giving up on a callback."


class _Server(ThreadingHTTPServer):
    """Test server that can be told what release payload or wheel to hand out."""

    release_payload: bytes = b'{"unexpected": true}'
    "Body served for /repos paths. Tests overwrite this to shape the updater result."

    wheel_bytes: bytes = b""
    "Body served for any .whl path, so a synthetic wheel can be 'downloaded'."

    @override
    def handle_error(self, request: object, client_address: object) -> None:
        # Tests abort downloads on purpose, which makes the handler thread see a
        # reset connection. That is expected here, so keep the tracebacks quiet.
        pass


class _Handler(BaseHTTPRequestHandler):
    protocol_version: str = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path == "/payload":
            self._send_all(PAYLOAD)
        elif path == "/headers":
            import json

            body = json.dumps({k.lower(): v for k, v in self.headers.items()}).encode()
            self._send_all(body)
        elif path == "/missing":
            self._empty(404)
        elif path.startswith("/file/"):
            self._send_slowly(int(path.rsplit("/", 1)[-1]), chunk=64 * 1024, delay=0.0)
        elif path.startswith("/slow/"):
            self._send_slowly(int(path.rsplit("/", 1)[-1]), chunk=512, delay=0.05)
        elif path.startswith("/repos/"):
            self._send_all(cast("_Server", self.server).release_payload)
        elif path.endswith(".whl"):
            self._send_all(cast("_Server", self.server).wheel_bytes)
        else:
            self._empty(404)

    def _empty(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_all(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        _ = self.wfile.write(body)

    def _send_slowly(self, size: int, chunk: int, delay: float) -> None:
        self.send_response(200)
        self.send_header("Content-Length", str(size))
        self.end_headers()
        remaining = size
        while remaining > 0:
            try:
                _ = self.wfile.write(b"\0" * min(chunk, remaining))
                self.wfile.flush()
            except OSError:
                # The client hung up, which is exactly what a cancel test does.
                return
            remaining -= chunk
            time.sleep(delay)

    @override
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


@pytest.fixture(scope="session")
def qt_app() -> Iterator[QCoreApplication]:
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


@pytest.fixture(scope="session")
def payload() -> bytes:
    return PAYLOAD


@pytest.fixture(scope="session")
def file_size() -> int:
    return FILE_SIZE


@pytest.fixture(scope="session")
def pump_until() -> Callable[[Callable[[], bool]], bool]:
    """Spins the Qt event loop until the predicate holds or the timeout expires."""

    def _pump(predicate: Callable[[], bool]) -> bool:
        app = QCoreApplication.instance()
        deadline = time.monotonic() + PUMP_TIMEOUT_S
        while time.monotonic() < deadline:
            if predicate():
                return True
            if app is not None:
                app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 10)
            else:
                time.sleep(0.005)
        return predicate()

    return _pump


@pytest.fixture(scope="session")
def http_server() -> Iterator[_Server]:
    server = _Server(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture(scope="session")
def base_url(http_server: _Server) -> str:
    return f"http://127.0.0.1:{http_server.server_port}"


@pytest.fixture
def client(qt_app: QCoreApplication, monkeypatch: pytest.MonkeyPatch) -> Iterator[NetworkClient]:  # pyright: ignore[reportUnusedParameter]
    """A NetworkClient with no leftover state from other tests."""
    monkeypatch.setattr(args, "offline", False)
    monkeypatch.delitem(SingletonMeta._instances, NetworkClient, raising=False)  # pyright: ignore[reportPrivateUsage]

    saved_urls = dict(NetworkClient._base_urls)  # pyright: ignore[reportPrivateUsage]
    NetworkClient._base_urls.clear()  # pyright: ignore[reportPrivateUsage]
    try:
        network = NetworkClient()
        yield network
        network.cancel_all()
    finally:
        NetworkClient._base_urls.clear()  # pyright: ignore[reportPrivateUsage]
        NetworkClient._base_urls.update(saved_urls)  # pyright: ignore[reportPrivateUsage]


@pytest.fixture
def offline(client: NetworkClient, monkeypatch: pytest.MonkeyPatch) -> NetworkClient:
    monkeypatch.setattr(args, "offline", True)
    return client
