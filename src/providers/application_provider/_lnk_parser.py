from __future__ import annotations

import logging
import os
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pylnk3  # pyright: ignore[reportMissingTypeStubs]

logger = logging.getLogger(__name__)

_WS_RE = re.compile(r"\s+")

DEFAULT_PER_FILE_TIMEOUT = 3.0
"Max seconds a single .lnk parse may take before it is abandoned and skipped."
DEFAULT_OVERALL_TIMEOUT = 60.0
"Max seconds a batch parse may take in total."


def _norm_value(value: str | None) -> str | None:
    "Collapses whitespace and normalizes case, or returns None if empty."
    if value is None:
        return None
    collapsed = _WS_RE.sub(" ", value).strip()
    return collapsed.casefold() if collapsed else None


def _norm_path(value: str | None) -> str | None:
    "Expands env vars and normalizes a path string for comparison, or returns None if empty."
    if value is None:
        return None
    expanded = os.path.expandvars(value).strip()
    if not expanded:
        return None
    return os.path.normcase(os.path.normpath(expanded))


@dataclass(kw_only=True)
class LnkDetail:
    "Parsed details of a Windows .lnk (Shell Link) file."

    name: str
    lnk_path: Path
    target: str | None = None
    "Target path as stored in the shortcut (may contain env vars)."
    target_resolved: Path | None = None
    "Target path with env vars expanded, when resolvable."
    arguments: str | None = None
    working_dir: str | None = None
    "The 'Start in' directory as stored in the shortcut."
    working_dir_resolved: Path | None = None
    description: str | None = None
    icon_location: str | None = None
    icon_index: int | None = None
    creation_time: datetime | None = None
    access_time: datetime | None = None
    write_time: datetime | None = None
    extra_data: dict[str, object] = field(default_factory=dict)

    @property
    def dedupe_key(self) -> tuple[str, str, str, str]:
        "Normalized (name, target, arguments, working_dir) tuple used to compare launch params."
        return (
            _norm_value(self.name) or "",
            _norm_path(self.target) or "",
            _norm_value(self.arguments) or "",
            _norm_path(self.working_dir) or "",
        )


def _resolve(value: str | None) -> Path | None:
    if value is None:
        return None
    expanded = os.path.expandvars(value).strip().strip('"')
    if not expanded:
        return None
    return Path(expanded)


# region temporary solution until https://github.com/strayge/pylnk/issues/50 fixed
# pylnk3 reads C-strings by looping until a NUL terminator, with no EOF check.
# On truncated/corrupt shortcuts buf.read() returns b"" forever and pylnk3 hangs
# in an infinite loop. Replace those readers with EOF-guarded versions that raise.
def _patch_pylnk3() -> None:
    if getattr(pylnk3, "_prospero_eof_guarded", False):
        return

    def read_cunicode(buf) -> str:
        parts: list[bytes] = []
        while True:
            b = buf.read(2)
            if not b:
                raise EOFError("truncated unicode string in shortcut")
            if b == b"\x00\x00":
                break
            parts.append(b)
        return b"".join(parts).decode("utf-16-le")

    def read_cstring(buf, padding: bool = False) -> str:
        parts: list[bytes] = []
        while True:
            b = buf.read(1)
            if not b:
                raise EOFError("truncated string in shortcut")
            if b == b"\x00":
                break
            parts.append(b)
        if padding and not len(parts) % 2:
            buf.read(1)
        return b"".join(parts).decode(pylnk3.DEFAULT_CHARSET)

    pylnk3.read_cunicode = read_cunicode
    pylnk3.read_cstring = read_cstring
    pylnk3._prospero_eof_guarded = True  # pyright: ignore[reportAttributeAccessIssue]


_patch_pylnk3()


def _stream_size(f) -> int:
    try:
        return os.fstat(f.fileno()).st_size
    except (OSError, AttributeError):
        pass
    getbuffer = getattr(f, "getbuffer", None)
    if getbuffer is not None:
        try:
            return getbuffer().nbytes
        except (AttributeError, ValueError):
            pass
    try:
        pos = f.tell()
        end = f.seek(0, 2)
        f.seek(pos)
        return end
    except (OSError, AttributeError):
        pass
    return 0


class _BoundedReader:
    """File-like wrapper that guards a parse against runaway reads.

    The EOF-patched readers raise the moment the underlying file is exhausted, so
    parsers cannot spin on an empty buffer. As a second line of defense the wrapper
    also raises once a wall-clock deadline or byte budget is exceeded. pylnk3 only
    needs read/seek/tell, which are forwarded.
    """

    _BUFFER_FACTOR = 2
    _SLACK = 64

    def __init__(self, f, *, deadline: float | None = None) -> None:
        self._f = f
        self._deadline = deadline
        self._budget = _stream_size(f) * self._BUFFER_FACTOR + self._SLACK
        self._read = 0

    def read(self, size: int = -1) -> bytes:
        if self._deadline is not None and time.monotonic() >= self._deadline:
            raise EOFError("shortcut parse deadline exceeded")
        if size < 0 or self._read + size > self._budget:
            size = max(0, self._budget - self._read)
        data = self._f.read(size)
        self._read += len(data)
        if size > 0 and len(data) < size:
            raise EOFError("shortcut data truncated")
        return data

    def seek(self, *args, **kwargs) -> int:
        return self._f.seek(*args, **kwargs)

    def tell(self) -> int:
        return self._f.tell()


# endregion


def parse_lnk(lnk_path: Path, *, timeout: float | None = None) -> LnkDetail | None:
    "Parses a single .lnk file into LnkDetail, or returns None on failure."

    deadline = time.monotonic() + timeout if timeout is not None else None
    try:
        with open(lnk_path, "rb") as f:
            lnk = pylnk3.parse(_BoundedReader(f, deadline=deadline))  # pyright: ignore[reportUnknownMemberType]
    except EOFError:
        logger.warning("Failed to parse lnk: %s", lnk_path)
        return None
    except Exception:
        logger.warning("Failed to parse lnk: %s", lnk_path, exc_info=True)
        return None

    target = getattr(lnk, "path", None) or getattr(getattr(lnk, "link_info", None), "path", None)

    extra: dict[str, object] = {}
    if hasattr(lnk, "shell_item_id_list"):
        extra["shell_item_id_list"] = lnk.shell_item_id_list
    if hasattr(lnk, "relative_path"):
        extra["relative_path"] = lnk.relative_path  # pyright: ignore[reportUnknownMemberType]
    if hasattr(lnk, "show_command"):
        extra["show_command"] = lnk.show_command  # pyright: ignore[reportAny]

    return LnkDetail(
        name=lnk_path.stem,
        lnk_path=lnk_path,
        target=target,
        target_resolved=_resolve(target),
        arguments=getattr(lnk, "arguments", None),
        working_dir=(
            wd
            if (wd := getattr(lnk, "work_dir", None) or getattr(lnk, "working_dir", None))
            else None
        ),
        working_dir_resolved=_resolve(
            getattr(lnk, "work_dir", None) or getattr(lnk, "working_dir", None)
        ),
        description=getattr(lnk, "description", None),
        icon_location=getattr(lnk, "icon", None),
        icon_index=getattr(lnk, "icon_index", None),
        creation_time=getattr(lnk, "creation_time", None),
        access_time=getattr(lnk, "access_time", None),
        write_time=getattr(lnk, "modification_time", None),
        extra_data=extra,
    )


def parse_lnks(
    lnk_paths: Iterable[Path],
    *,
    per_file_timeout: float | None = DEFAULT_PER_FILE_TIMEOUT,
    overall_timeout: float | None = DEFAULT_OVERALL_TIMEOUT,
) -> list[LnkDetail]:
    """Parses multiple .lnk files, skipping failures and files that time out.

    A hard budget is applied to each file via parse_lnk, and the batch stops early
    once overall_timeout has elapsed. Passing None disables the corresponding limit.
    """
    paths = list(lnk_paths)
    start = time.monotonic()
    results: list[LnkDetail] = []
    for path in paths:
        if overall_timeout is not None:
            remaining = overall_timeout - (time.monotonic() - start)
            if remaining <= 0:
                logger.warning(
                    "lnk batch parse hit overall timeout %.1fs; stopping", overall_timeout
                )
                break
            per_file = per_file_timeout if per_file_timeout is not None else remaining
            per_file = min(per_file, remaining)
        else:
            per_file = per_file_timeout
        detail = parse_lnk(path, timeout=per_file)
        if detail is not None:
            results.append(detail)
    return results


def dedupe_lnks(lnks: Iterable[LnkDetail]) -> list[LnkDetail]:
    "Removes lnks sharing the same normalized name/target/arguments/working_dir, keeping the first."
    seen: set[tuple[str, str, str, str]] = set()
    result: list[LnkDetail] = []
    for lnk in lnks:
        key = lnk.dedupe_key
        if key in seen:
            logger.debug("Dropping duplicate lnk: %s", lnk.lnk_path)
            continue
        seen.add(key)
        result.append(lnk)
    return result
