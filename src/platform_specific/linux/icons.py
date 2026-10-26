"""Linux/other-platform icon loading.

It is deliberately thread-safe: ``QImage`` can be created off the GUI thread, unlike ``QPixmap``.
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPainter

from data_objects import IconLoadMethod, LoadMethod

fallback_dirs = [  # TODO: add fallback_dirs from config
    "/usr/share/pixmaps/",
    "~/.local/share/pixmaps/",
]
QIcon.setFallbackSearchPaths(fallback_dirs)


def load_icon(icon_load_method: IconLoadMethod, size: int = 32) -> QImage | None:
    """Resolve an :class:`IconLoadMethod` on Linux."""
    method, path = icon_load_method.load_method, icon_load_method.file_path

    if method is LoadMethod.linux_find and (lf := icon_load_method.linux_find) is not None:
        ic = QIcon.fromTheme(lf)
        si = QSize(0, 0)
        for si in sorted(ic.availableSizes(), key=lambda x: x.width()):
            if si.width() < size:
                continue
            break
        if si == QSize(0, 0):
            return None
        img = QImage(si, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        with QPainter(img) as p:
            ic.paint(p, img.rect())
        return img

    if method in {LoadMethod.default, LoadMethod.loading} or path is None:
        return None

    if method is LoadMethod.load_file:
        image = QImage(str(path))
        return None if image.isNull() else image

    return None


__all__ = ["load_icon"]
