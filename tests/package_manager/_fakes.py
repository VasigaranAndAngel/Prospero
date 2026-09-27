"""Helpers for building throwaway wheels in tests.

Kept out of conftest so test modules can import them normally.
"""

import base64
import hashlib
import zipfile
from collections.abc import Mapping
from pathlib import Path

import pytest

from package_manager._allowlist import PILLOW, AllowedWheel

WHEEL_NAME: str = "pillow-12.3.0-cp312-cp312-win_amd64.whl"
"Filename the allowlist expects, so its tags and dist-info name line up."

MEMBERS: Mapping[str, bytes] = {
    "PIL/__init__.py": b'__version__ = "12.3.0"\n',
    "PIL/ImageCms.py": b'NAME = "stand-in for the real ImageCms"\n',
    "pillow-12.3.0.dist-info/METADATA": b"Metadata-Version: 2.1\nName: pillow\n",
    "pillow-12.3.0.dist-info/WHEEL": b"Wheel-Version: 1.0\n",
    "pillow-12.3.0.dist-info/top_level.txt": b"PIL\n",
}

ALLOWED_TOP_LEVEL: frozenset[str] = frozenset({"PIL", "pillow-12.3.0.dist-info"})

RECORD_PATH: str = "pillow-12.3.0.dist-info/RECORD"
"The RECORD member name, which is generated rather than listed by hand."


def make_record(members: Mapping[str, bytes]) -> bytes:
    """Builds a RECORD that lists every other member the way a real wheel does.

    Args:
        members (Mapping[str, bytes]): Archive member name to content.

    Returns:
        bytes: Comma separated record rows, without a RECORD row for itself.
    """
    rows = [
        f"{name},sha256={_digest_of(content)},{len(content)}"
        for name, content in sorted(members.items())
        if name != RECORD_PATH
    ]
    return ("\n".join(rows) + "\n").encode()


def _digest_of(content: bytes) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()


def build_wheel(
    path: Path, members: Mapping[str, bytes] | None = None, record: bytes | None = None
) -> Path:
    """Writes a wheel-shaped zip, with a matching RECORD, and returns its path.

    Args:
        path (Path): Where to write it. Parent directories are created.
        members (Mapping | None): Archive member name to content.
        record (bytes | None): RECORD to use verbatim, for testing rejection paths.

    Returns:
        Path: The written file.
    """
    content = dict(MEMBERS if members is None else members)
    content[RECORD_PATH] = make_record(content) if record is None else record

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in content.items():
            archive.writestr(name, payload)
    return path


def digest_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_wheel(
    monkeypatch: pytest.MonkeyPatch,
    wheel: Path,
    requires_python: str = ">=3.10",
    url: str | None = None,
) -> AllowedWheel:
    """Points the Pillow allowlist entry at a local wheel with its real digest.

    Args:
        monkeypatch (pytest.MonkeyPatch): Restores the original entry on teardown.
        wheel (Path): The wheel to make acceptable.
        requires_python (str): Spec set to claim, for testing that filter.
        url (str | None): Download url to record, defaulting to a file uri.

    Returns:
        AllowedWheel: The entry that was installed into the allowlist.
    """
    patched = AllowedWheel(
        filename=WHEEL_NAME,
        sha256=digest_of(wheel),
        size=wheel.stat().st_size,
        url=wheel.as_uri() if url is None else url,
        requires_python=requires_python,
    )
    monkeypatch.setitem(PILLOW.wheels, "win_amd64", patched)
    return patched
