from pathlib import Path

def expand_path(p):
    if isinstance(p, str):
        return Path(p).expanduser()
    try:
        return p.expanduser()
    except Exception:
        return p
