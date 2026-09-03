import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    _base_path = Path(getattr(sys, "_MEIPASS", Path()))
else:
    _base_path = Path(".")

ASSETS_PATH = Path(_base_path).absolute() / "assets"

_AP = ASSETS_PATH


DEFAULT_RESULT_ICON_PATH: Path = _AP / "indeterminate_question_box.svg"
APP_ICON_SVG: Path = _AP / "icon" / "icon.svg"
APP_ICON_PNG: Path = _AP / "icon" / "icon.png"
APP_ICON_ICO: Path = _AP / "icon" / "icon.ico"
