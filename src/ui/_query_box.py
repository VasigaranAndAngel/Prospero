from PySide6.QtWidgets import QLineEdit, QWidget


class QueryBox(QLineEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setFixedHeight(60)
        self.setContentsMargins(10, 10, 10, 10)

        font = self.font()
        font.setPointSize(int(font.pointSize() * 1.4))
        self.setFont(font)

        self.setStyleSheet('QLineEdit {background: "transparent"; border: "transparent"}')
