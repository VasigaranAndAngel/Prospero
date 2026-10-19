"""Linux/other-platform icon loading.

The application provider resolves freedesktop icon names to real files before handing
them over, so this implementation only has to load the image. It is deliberately
thread-safe: ``QImage`` can be created off the GUI thread, unlike ``QPixmap``.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QImage


def fetch_icon(filepath: Path, size: int = 32, use_generic_type: bool = False) -> QImage | None:
    """Load ``filepath`` as an icon image, or return None when it cannot be read.

    Args:
        filepath (Path): Image file to load.
        size (int): Requested icon size. Accepted for API parity; the image is loaded as-is.
        use_generic_type (bool): Accepted for API parity; unused off Windows.

    Returns:
        QImage | None: The loaded image, or None when the file is not a readable image.
    """
    _ = size, use_generic_type
    image = QImage(str(filepath))
    return None if image.isNull() else image
