from __future__ import annotations

import io
import logging
import os
import time
import winreg
from pathlib import Path
from typing import TYPE_CHECKING

import olefile
import pylnk3

try:
    import pythoncom
    from win32com.propsys import propsys, pscon
except ImportError:  # pragma: no cover
    pythoncom = None
    propsys = None
    pscon = None

from data_objects import IconLoadMethod, LoadMethod

from .._types import Launch, RecentFile
from ._lnk_parser import LnkDetail, _BoundedReader, _patch_pylnk3

if TYPE_CHECKING:
    from .._types import AppDetail

logger = logging.getLogger(__name__)

POLY64 = 0x92C64265D32139A4

DEST_FOLDER = Path(os.environ["APPDATA"]) / r"Microsoft\Windows\Recent\AutomaticDestinations"
"Jump list files Windows keeps for each app's recent documents."

MAX_RECENT_FILES = 1000
"Max recent files to collect per app. TODO: make adjustable via configs."

_STREAM_TIMEOUT = 10.0
"Max seconds to spend parsing a single jump list file."

_STREAM_MAGIC = b"\x4c\x00\x00\x00"
"Magic prefix of a serialized .LNK stream inside an OLE jump list."


def crc64_table(poly):
    table = []
    for i in range(256):
        val = i
        for _ in range(8):
            val = (val >> 1) ^ poly if val & 1 else val >> 1
        table.append(val)
    return table


CRCTABLE = crc64_table(POLY64)


def appid_hex(appid: str) -> str:
    "Computes the 16-hex jump list AppID for the given AppID string."
    crc = 0xFFFFFFFFFFFFFFFF
    for b in appid.upper().encode("utf-16-le"):
        crc = (crc >> 8) ^ CRCTABLE[(crc ^ b) & 0xFF]
    return f"{crc & 0xFFFFFFFFFFFFFFFF:016x}"


def build_appid_map() -> dict[str, str]:
    "Maps jump list AppID hashes to the AppID strings Windows has recorded."
    mapping: dict[str, str] = {}
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Search\JumplistData",
        )
    except OSError:
        return mapping
    i = 0
    while True:
        try:
            name, _, _ = winreg.EnumValue(key, i)
        except OSError:
            break
        i += 1
        mapping[appid_hex(name)] = name
    return mapping


FOLDER_GUIDS = {
    "windir": "{F38BF404-1D43-42F2-9305-67DE0B28FC23}",
    "system": "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}",
    "systemx86": "{D65231B0-B2F1-4857-A4CE-A8E7C6EA7D27}",
    "progfiles": "{905E63B6-C1BF-494E-B29C-65B732D3D21A}",
    "progfilesx64": "{6D809377-6AF0-444B-8957-A3773F02200E}",
    "progfilesx86": "{7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}",
    "appdata": "{3EB685DB-65F9-4CF6-A03A-E3EF65729F3D}",
    "localappdata": "{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}",
    "localavg_programs": "{5CD7AEE2-2219-4A67-B85D-6C9CE15660CB}",
    "userprofile": "{5E6C858F-0E22-4760-9AFE-EA3317B67173}",
}


def normalize_variants(exe: str) -> list[str]:
    "Returns exe plus known-folder {GUID}-prefixed variants Windows may have stored."
    variants = [exe]
    low = exe.lower()
    win = os.environ["WINDIR"].rstrip("\\").lower()
    pf = os.environ.get("ProgramFiles", "").rstrip("\\").lower()
    pf86 = os.environ.get("ProgramFiles(x86)", "").rstrip("\\").lower()
    la = os.environ.get("LOCALAPPDATA", "").rstrip("\\").lower()
    appdata = os.environ.get("APPDATA", "").rstrip("\\").lower()
    profile = os.environ.get("USERPROFILE", "").rstrip("\\").lower()

    def sub(prefix, repl, head=""):
        anchor = prefix + ("\\" + head if head else "")
        if low.startswith(anchor.lower() + "\\") or low == anchor.lower():
            variants.append(repl + exe[len(anchor) :])

    sub(win + "\\system32", FOLDER_GUIDS["system"])
    sub(win + "\\SysWOW64", FOLDER_GUIDS["systemx86"])
    sub(win, FOLDER_GUIDS["windir"])
    for g in ("progfiles", "progfilesx64", "progfilesx86"):
        sub(pf, FOLDER_GUIDS[g])
        sub(pf86, FOLDER_GUIDS[g])
    sub(la + "\\Programs", FOLDER_GUIDS["localavg_programs"])
    sub(la, FOLDER_GUIDS["localappdata"])
    sub(appdata, FOLDER_GUIDS["appdata"])
    sub(profile, FOLDER_GUIDS["userprofile"])
    return variants


def _appid_candidates(detail: AppDetail) -> set[str]:
    "Candidate jump list hashes for an app, or empty set when none can be derived."
    candid: set[str] = set()
    if detail.type == "uwp" and detail.app_id:
        candid.add(appid_hex(detail.app_id))
        return candid

    ld = detail.lnk_detail
    if not isinstance(ld, LnkDetail) or ld.target is None:
        return candid
    candid.add(appid_hex(ld.target))
    expanded = os.path.expandvars(ld.target).strip().strip('"')
    if expanded:
        candid.add(appid_hex(expanded))
        for variant in normalize_variants(expanded):
            candid.add(appid_hex(variant))
    return candid


_com_initialized: bool = False
"Whether COM was initialized on the current worker thread."


def _app_user_model_id(lnk_path: Path) -> str | None:
    """Best-effort read of System.AppUserModel.ID from a shortcut's property store.

    Apps like Electron/Ghost frameworks record a custom AppUserModelID on their
    shortcut, which is what Windows uses as the jump list AppID. Their jump lists
    then never match the exe-path candidates.
    """
    global _com_initialized
    if propsys is None:
        return None
    if not _com_initialized:
        try:
            pythoncom.CoInitialize()
        except Exception:
            return None
        _com_initialized = True
    try:
        store = propsys.SHGetPropertyStoreFromParsingName(os.fspath(lnk_path))
        variant = store.GetValue(pscon.PKEY_AppUserModel_ID)
        if variant and variant.vt == 31:
            value = variant.GetValue()
            if isinstance(value, str) and value:
                return value
    except Exception:
        logger.debug("AppUserModelID read failed for %s", lnk_path, exc_info=True)
    return None


_dest_prefixes: set[str] | None = None


def _jumplist_prefixes() -> set[str]:
    "All AppID hashes that have a jump list file on disk, cached; built atomically."
    global _dest_prefixes
    if _dest_prefixes is not None:
        return _dest_prefixes
    result: set[str] = set()
    try:
        for f in DEST_FOLDER.iterdir():
            if f.name.endswith(".automaticDestinations-ms") and f.stat().st_size:
                result.add(f.name[:16])
    except OSError:
        pass
    _dest_prefixes = result
    return result


def _cached_recent_paths(doc_path: Path) -> list[Path]:
    cached = _PARSED_CACHE.get(doc_path)
    if cached is None:
        cached = _iter_recent_file_paths(doc_path, time.monotonic() + _STREAM_TIMEOUT)
        _PARSED_CACHE[doc_path] = cached
    return cached


def _iter_recent_file_paths(doc_path: Path, deadline: float) -> list[Path]:
    "Extracts recent document paths from a jump list file, in stream order."
    results: list[Path] = []
    try:
        with olefile.OleFileIO(doc_path) as ole:
            for stream in ole.listdir():
                data = ole.openstream(stream).read()
                if data[:4] != _STREAM_MAGIC:
                    continue
                try:
                    lnk = pylnk3.parse(_BoundedReader(io.BytesIO(data), deadline=deadline))
                except Exception:
                    logger.debug("Skipping unparsable stream in %s", doc_path)
                    continue
                target = getattr(lnk, "path", None)
                if not target:
                    target = getattr(getattr(lnk, "link_info", None), "path", None)
                if not target:
                    continue
                results.append(Path(target))
    except OSError:
        return []
    return results


_PARSED_CACHE: dict[Path, list[Path]] = {}


def get_recent_files(details: list[AppDetail]) -> list[AppDetail]:
    "Fills recent_file on each app matched to a jump list and returns the list."
    _patch_pylnk3()
    prefixes = _jumplist_prefixes()
    if not prefixes:
        return details

    seen: set[str] = set()
    for detail in details:
        candidates = _appid_candidates(detail)
        matched = prefixes & candidates
        if not matched and detail.type == "desktop" and detail.path is not None:
            aumid = _app_user_model_id(detail.path)
            if aumid:
                matched = prefixes & {appid_hex(aumid)}
        matched = sorted(matched)
        if not matched:
            continue
        recents: list[Path] = []
        for prefix in matched:
            recents.extend(_cached_recent_paths(DEST_FOLDER / f"{prefix}.automaticDestinations-ms"))

        unique: list[Path] = []
        for p in recents:
            key = os.path.normcase(os.path.normpath(p))
            if key in seen:
                continue
            seen.add(key)
            if p.exists():
                unique.append(p)
            if len(unique) >= MAX_RECENT_FILES:
                break
        if unique:
            detail.recent_files = [
                RecentFile(
                    p.name,
                    Launch(f'start "" "{p}"', shell=True),
                    path=p,
                    icon=IconLoadMethod(LoadMethod.win32api, p),
                )
                for p in unique
            ]
    return details

