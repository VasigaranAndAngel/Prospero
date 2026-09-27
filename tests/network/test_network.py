"""Tests for the shared network client.

Everything here either avoids the network entirely (url building, offline refusal) or talks to the
local test server from conftest.
"""

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from network import OFFLINE_ERROR, USER_AGENT, Downloaded, NetworkClient, NetworkError

TPump = Callable[[Callable[[], bool]], bool]


# region base urls


def test_resolve_uses_default_base() -> None:
    resolved = NetworkClient.resolve("github", "https://api.github.com", "repos/a/b/releases")

    assert resolved == "https://api.github.com/repos/a/b/releases"


def test_resolve_honours_override() -> None:
    NetworkClient.set_base_url("github", "https://mirror.test/api/")

    resolved = NetworkClient.resolve("github", "https://api.github.com", "repos/a/b/releases")

    assert resolved == "https://mirror.test/api/repos/a/b/releases"


def test_resolve_returns_bare_base_without_path() -> None:
    assert NetworkClient.resolve("pypi", "https://pypi.org") == "https://pypi.org"


def test_set_base_url_none_clears_override() -> None:
    NetworkClient.set_base_url("github", "https://mirror.test")
    NetworkClient.set_base_url("github", None)

    assert (
        NetworkClient.resolve("github", "https://api.github.com", "x") == "https://api.github.com/x"
    )


def test_override_does_not_leak_between_services() -> None:
    NetworkClient.set_base_url("github", "https://mirror.test")

    assert NetworkClient.resolve("pypi", "https://pypi.org", "p") == "https://pypi.org/p"


def test_unknown_service_falls_back_to_default() -> None:
    assert NetworkClient.resolve("whatever", "https://fallback.test").startswith("https://fallback")


# endregion


# region offline


def test_offline_fetch_reports_error(offline: NetworkClient) -> None:
    results: list[bytes | NetworkError] = []

    offline.fetch("https://api.github.com/whatever", results.append)

    assert len(results) == 1
    assert isinstance(results[0], NetworkError)
    assert results[0].error_str == OFFLINE_ERROR
    assert results[0].aborted is False


def test_offline_download_reports_aborted(offline: NetworkClient, tmp_path: Path) -> None:
    states: list[Downloaded] = []
    target = tmp_path / "thing.bin"

    offline.download("https://example.com/thing.bin", target, states.append)

    assert len(states) == 1
    assert states[0].aborted is True
    assert states[0].completed is False
    assert not target.exists(), "nothing should be written while offline"


def test_offline_starts_no_request(offline: NetworkClient) -> None:
    offline.fetch("https://example.com/x")

    assert offline.active() == []


# endregion


# region fetch


def test_fetch_delivers_payload(
    client: NetworkClient, base_url: str, payload: bytes, pump_until: TPump
) -> None:
    results: list[bytes | NetworkError] = []
    signals: list[tuple[str, object]] = []
    _ = client.fetched.connect(lambda url, result: signals.append((url, result)))  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]

    client.fetch(f"{base_url}/payload", results.append)

    assert pump_until(lambda: len(results) == 1), "fetch never completed"
    assert results[0] == payload
    assert signals == [(f"{base_url}/payload", payload)]


def test_fetch_sends_user_agent(client: NetworkClient, base_url: str, pump_until: TPump) -> None:
    results: list[bytes | NetworkError] = []

    client.fetch(f"{base_url}/headers", results.append)

    assert pump_until(lambda: len(results) == 1)
    assert isinstance(results[0], bytes)
    assert json.loads(results[0])["user-agent"] == USER_AGENT


def test_fetch_404_carries_status(client: NetworkClient, base_url: str, pump_until: TPump) -> None:
    results: list[bytes | NetworkError] = []

    client.fetch(f"{base_url}/missing", results.append)

    assert pump_until(lambda: len(results) == 1)
    error = results[0]
    assert isinstance(error, NetworkError)
    assert error.status == 404
    assert "404" in error.error_str
    assert error.aborted is False


def test_fetch_unreachable_host(client: NetworkClient, pump_until: TPump) -> None:
    results: list[bytes | NetworkError] = []

    # Port 1 on loopback refuses connections, so this fails without leaving the machine.
    client.fetch("http://127.0.0.1:1/nope", results.append, timeout_ms=5_000)

    assert pump_until(lambda: len(results) == 1)
    assert isinstance(results[0], NetworkError)
    assert results[0].aborted is False


def test_cancel_stops_fetch_and_reports_aborted(client: NetworkClient, pump_until: TPump) -> None:
    results: list[bytes | NetworkError] = []
    url = "http://127.0.0.1:1/slow"

    client.fetch(url, results.append)
    client.cancel(url)

    assert pump_until(lambda: len(results) == 1)
    assert isinstance(results[0], NetworkError)
    assert results[0].aborted is True


def test_fetch_clears_active_when_done(
    client: NetworkClient, base_url: str, pump_until: TPump
) -> None:
    results: list[bytes | NetworkError] = []

    client.fetch(f"{base_url}/payload", results.append)
    assert pump_until(lambda: len(results) == 1)

    assert client.active() == []


# endregion


# region download


def test_download_writes_file_and_completes(
    client: NetworkClient, base_url: str, file_size: int, tmp_path: Path, pump_until: TPump
) -> None:
    states: list[Downloaded] = []
    target = tmp_path / "nested" / "file.bin"

    client.download(f"{base_url}/file/{file_size}", target, states.append)

    assert pump_until(lambda: any(s.completed for s in states)), "download never completed"
    final = states[-1]
    assert final.completed is True
    assert final.aborted is False
    assert final.downloaded_size == file_size
    assert final.download_progress == 1.0
    assert target.read_bytes() == b"\0" * file_size


def test_download_reports_intermediate_progress(
    client: NetworkClient, base_url: str, file_size: int, tmp_path: Path, pump_until: TPump
) -> None:
    states: list[Downloaded] = []

    client.download(f"{base_url}/file/{file_size}", tmp_path / "f.bin", states.append)

    assert pump_until(lambda: any(s.completed for s in states))
    progress = [s for s in states if not s.completed]
    assert progress, "expected at least one in flight progress report"
    assert all(0.0 <= s.download_progress <= 1.0 for s in states)
    assert all(s.total_size == file_size for s in progress)
    assert all(s.speed is not None and s.speed > 0 for s in progress)


def test_download_leaves_no_partial_file_behind(
    client: NetworkClient, base_url: str, file_size: int, tmp_path: Path, pump_until: TPump
) -> None:
    states: list[Downloaded] = []
    target = tmp_path / "f.bin"

    client.download(f"{base_url}/file/{file_size}", target, states.append)

    assert pump_until(lambda: any(s.completed for s in states))
    assert [p.name for p in tmp_path.iterdir()] == ["f.bin"]


def test_cancel_download_removes_partial_and_reports_aborted(
    client: NetworkClient, base_url: str, file_size: int, tmp_path: Path, pump_until: TPump
) -> None:
    states: list[Downloaded] = []
    target = tmp_path / "slow.bin"
    url = f"{base_url}/slow/{file_size}"

    client.download(url, target, states.append)
    assert pump_until(lambda: any(s.downloaded_size > 0 for s in states)), "nothing arrived"
    client.cancel(url)

    assert pump_until(lambda: any(s.aborted for s in states)), "cancel never reported"
    assert not target.exists(), "partial download should be cleaned up"
    assert not list(tmp_path.glob("*.part")), "part file should be removed"


def test_download_into_unwritable_location_reports_aborted(
    client: NetworkClient, base_url: str, file_size: int, tmp_path: Path
) -> None:
    states: list[Downloaded] = []
    blocker = tmp_path / "blocker"
    _ = blocker.write_text("not a directory")

    client.download(f"{base_url}/file/{file_size}", blocker / "f.bin", states.append)

    assert len(states) == 1
    assert states[0].aborted is True


def test_download_carries_url_in_state(
    client: NetworkClient, base_url: str, file_size: int, tmp_path: Path, pump_until: TPump
) -> None:
    states: list[Downloaded] = []
    url = f"{base_url}/file/{file_size}"

    client.download(url, tmp_path / "f.bin", states.append)

    assert pump_until(lambda: any(s.completed for s in states))
    assert all(s.url == url for s in states)


@pytest.mark.parametrize("bad", ["", "not-a-url"])
def test_malformed_url_reports_error(client: NetworkClient, pump_until: TPump, bad: str) -> None:
    results: list[bytes | NetworkError] = []

    client.fetch(bad, results.append)

    assert pump_until(lambda: len(results) == 1)
    assert isinstance(results[0], NetworkError)


# endregion
