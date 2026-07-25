from typing import override

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QScrollArea


class ResultsBox(QScrollArea):
    @override
    def minimumSizeHint(self, /) -> QSize:
        return QSize(0, 0)
