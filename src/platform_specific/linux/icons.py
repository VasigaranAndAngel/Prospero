"""Linux/other-platform icon loading.

The application provider resolves freedesktop icon names to real files before handing
them over, so this implementation only has to load the image. It is deliberately
thread-safe: ``QImage`` can be created off the GUI thread, unlike ``QPixmap``.
"""

from PySide6.QtGui import QImage

from data_objects import IconLoadMethod, LoadMethod


def load_icon(icon_load_method: IconLoadMethod, size: int = 32) -> QImage | None:
    """Resolve an :class:`IconLoadMethod` on Linux.

    The app provider already resolved freedesktop icon names to files, so only the
    ``load_file`` case is meaningful here.
    """
    method, path = icon_load_method.load_method, icon_load_method.file_path
    if method in {LoadMethod.default, LoadMethod.loading} or path is None:
        return None
    if method is LoadMethod.load_file:
        image = QImage(str(path))
        return None if image.isNull() else image
    return None


__all__ = ["load_icon"]
