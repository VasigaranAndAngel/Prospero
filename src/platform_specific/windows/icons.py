import ctypes
from ctypes import wintypes
from pathlib import Path

import win32gui
import win32ui
from PySide6.QtGui import QImage

from data_objects import IconLoadMethod, LoadMethod

_SHGFI_ICON = 0x000000100
_SHGFI_LARGEICON = 0x000000000
_SHGFI_SMALLICON = 0x000000001
_SHGFI_USEFILEATTRIBUTES = 0x000000010
_FILE_ATTRIBUTE_NORMAL = 0x80
_SHGFI_PIDL = 0x8


class _SH_FILE_INFO(ctypes.Structure):
    _fields_ = [
        ("hIcon", wintypes.HICON),
        ("iIcon", ctypes.c_int),
        ("dwAttributes", wintypes.DWORD),
        ("szDisplayName", ctypes.c_wchar * 260),
        ("szTypeName", ctypes.c_wchar * 80),
    ]


_SHGetFileInfoW = ctypes.windll.shell32.SHGetFileInfoW
_SHGetFileInfoW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.POINTER(_SH_FILE_INFO),
    ctypes.c_uint,
    ctypes.c_uint,
]
_SHGetFileInfoW.restype = ctypes.c_uint


def _get_hicon(filepath: str, size: int = 32, use_generic_type: bool = False) -> int:
    flags = _SHGFI_ICON | (_SHGFI_SMALLICON if size <= 16 else _SHGFI_LARGEICON)
    file_attrs: int = 0

    if use_generic_type:
        flags |= _SHGFI_USEFILEATTRIBUTES
        file_attrs = _FILE_ATTRIBUTE_NORMAL

    info = _SH_FILE_INFO()
    res = _SHGetFileInfoW(filepath, file_attrs, ctypes.byref(info), ctypes.sizeof(info), flags)
    if not res or not info.hIcon:
        raise RuntimeError(f"Could not get icon for {filepath}")
    return info.hIcon


def _hicon_to_qimage(hicon: int, size: int = 32) -> QImage:
    hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
    hbmp = win32ui.CreateBitmap()
    hbmp.CreateCompatibleBitmap(hdc, size, size)
    hdc_mem = hdc.CreateCompatibleDC()
    hdc_mem.SelectObject(hbmp)
    hdc_mem.DrawIcon((0, 0), hicon)

    bmpinfo = hbmp.GetInfo()
    w, h = bmpinfo["bmWidth"], bmpinfo["bmHeight"]
    bmpstr = hbmp.GetBitmapBits(True)  # raw BGRA bytes

    win32gui.DestroyIcon(hicon)

    qimg = QImage(bmpstr, w, h, QImage.Format.Format_ARGB32)
    # Windows icon bitmaps are stored bottom-up; mirror vertically to fix it
    # qimg = qimg.mirrored(False, True)
    return qimg


def _try_get_icon(filepath: str, size: int, use_generic_type: bool) -> QImage | None:
    try:
        hicon = _get_hicon(filepath, size=size, use_generic_type=use_generic_type)
        return _hicon_to_qimage(hicon, size=size)
    except Exception:
        return None


def _fetch_icon(filepath: Path, size: int = 32, use_generic_type: bool = False) -> QImage | None:
    """Fetch icon with win32 api of a file and return it as QImage, or None on failure.

    Falls back to the generic type icon when the real file icon cannot be
    retrieved (e.g. broken shortcut target, non-existent path).
    """
    path = str(filepath)
    pixmap = _try_get_icon(path, size, use_generic_type)
    if pixmap is not None or use_generic_type:
        return pixmap
    return _try_get_icon(path, size, use_generic_type=True)


_shell32 = ctypes.windll.shell32

_shell32.SHParseDisplayName.argtypes = [
    wintypes.LPCWSTR,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_void_p),
    wintypes.ULONG,
    ctypes.POINTER(wintypes.ULONG),
]
_shell32.SHGetFileInfoW.argtypes = [
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(_SH_FILE_INFO),
    ctypes.c_uint,
    ctypes.c_uint,
]
_shell32.ILFree.argtypes = [ctypes.c_void_p]


def fetch_windows_app_icon(app_user_model_id: str, size: int = 32) -> QImage:
    "Retrieves the icon for a Windows application by its App User Model ID"
    shell_path = f"shell:AppsFolder\\{app_user_model_id}"

    pidl = ctypes.c_void_p()
    sfgao = wintypes.ULONG(0)
    hr = _shell32.SHParseDisplayName(shell_path, None, ctypes.byref(pidl), 0, ctypes.byref(sfgao))
    if hr != 0 or not pidl:
        raise RuntimeError(
            f"SHParseDisplayName failed (hr=0x{hr & 0xFFFFFFFF:08X}) for {app_user_model_id}"
        )

    try:
        flags = _SHGFI_ICON | _SHGFI_PIDL | (_SHGFI_SMALLICON if size <= 16 else _SHGFI_LARGEICON)
        info = _SH_FILE_INFO()
        res = _shell32.SHGetFileInfoW(pidl, 0, ctypes.byref(info), ctypes.sizeof(info), flags)
        if not res or not info.hIcon:
            raise RuntimeError(f"SHGetFileInfoW failed for {app_user_model_id}")
        return _hicon_to_qimage(info.hIcon, size)
    finally:
        _shell32.ILFree(pidl)


def load_icon(icon_load_method: IconLoadMethod, size: int = 32) -> QImage | None:
    """Resolve any :class:`IconLoadMethod` using the Windows shell APIs."""
    method, path = icon_load_method.load_method, icon_load_method.file_path

    if method is LoadMethod.win32api_windows_app:
        app_id = icon_load_method.app_id
        return fetch_windows_app_icon(app_id, size) if app_id is not None else None

    if method in {LoadMethod.default, LoadMethod.loading} or path is None:
        return None

    if method is LoadMethod.load_file:
        image = QImage(str(path))
        return None if image.isNull() else image

    return _fetch_icon(path, size=size, use_generic_type=method is LoadMethod.win32api_generic)


__all__ = ["fetch_windows_app_icon", "load_icon"]
