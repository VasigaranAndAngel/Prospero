from pathlib import Path

ASSETS_PATH = Path("assets").absolute()

_RP = ASSETS_PATH


DEFAULT_RESULT_ICON_PATH: Path = _RP / "indeterminate_question_box.svg"
APP_ICON_SVG: Path = _RP / "icon" / "icon.svg"
APP_ICON_PNG: Path = _RP / "icon" / "icon.png"
APP_ICON_ICO: Path = _RP / "icon" / "icon.ico"
