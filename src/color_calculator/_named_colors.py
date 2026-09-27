"""
Named colors kept in a user editable toml file, layered over ColorAide's CSS table.

ColorAide resolves a name through ``coloraide.css.color_names.name2val_map`` and memoizes the
tokenizer that looks names up, so replacing the names here means mutating that map in place and
clearing the tokenizer cache. Without the cache clear, a name that was already parsed keeps
resolving to the old value for the life of the process.
"""

import logging
import math
import tomllib
from pathlib import Path
from typing import Final

import tomli_w
from coloraide.css import color_names as _color_names
from coloraide.css.parse import tokenize_css

from constants import APPLICATION_NAME

logger = logging.getLogger(__name__)

DEFAULT_NAMED_COLORS_FILE: Final[Path] = (
    Path.home() / ".config" / APPLICATION_NAME.title() / "color" / "named_colors.toml"
)
"Where the named color table lives unless a config says otherwise."

RESERVED_NAMES: Final[frozenset[str]] = frozenset(
    {
        # Matched as css functions before names are tried, so an entry here would either
        # be unreachable or shadow the function.
        "color",
        "rgb",
        "rgba",
        "hsl",
        "hsla",
        "hwb",
        "lab",
        "lch",
        "oklab",
        "oklch",
        "jzazbz",
        "jzczhz",
        "ictcp",
        # Accepted inside a function as a missing channel, never as a whole color.
        "none",
    }
)
"""
Names ColorAide reserves. ``transparent`` is deliberately not here: it is a real entry in
ColorAide's own table, and seeding it while refusing to read it back would not round trip.
"""

_HEX_DIGITS: Final[frozenset[int]] = frozenset({3, 4, 6, 8})
"Accepted hex string lengths."


type Channel4 = tuple[float, float, float, float]
"""Red, green, blue and alpha in 0-255, the shape ColorAide's name table stores."""


def _to_hex(vector: Channel4) -> str:
    """Formats ColorAide's 0-255 channel tuple as a css hex string.

    Args:
        vector (Channel4): Channels as red, green, blue and alpha in 0-255.

    Returns:
        str: ``#rrggbb``, with alpha appended only when it is not fully opaque.
    """
    red, green, blue, alpha = vector
    digits = [max(0, min(255, math.floor(c))) for c in (red, green, blue)]
    hexed = "#" + "".join(f"{c:02x}" for c in digits)
    if alpha != 255:
        hexed += f"{max(0, min(255, math.floor(alpha))):02x}"
    return hexed


_CSS_DEFAULTS: Final[dict[str, str]] = {
    name: _to_hex(vector)  # pyright: ignore[reportArgumentType]
    for name, vector in _color_names.name2val_map.items()
}
"ColorAide's css names captured before any caller can replace them."


def _from_hex(value: str) -> Channel4:
    """Parses a css hex string into ColorAide's 0-255 channel tuple.

    Accepts the 3, 4, 6 and 8 digit forms ColorAide's own hex pattern accepts, with or without a
    leading ``#``. Shorter forms are shorthand, so ``#abc`` is ``#aabbcc``.

    Args:
        value (str): Hex color.

    Returns:
        Channel4: Red, green, blue and alpha in 0-255.

    Raises:
        ValueError: When the string is not an accepted hex color.
    """
    text = value.strip().removeprefix("#").lower()

    if len(text) in (3, 4):
        short = [int(c * 2, 16) for c in text]
        if len(short) == 3:
            return float(short[0]), float(short[1]), float(short[2]), 255.0
        return float(short[0]), float(short[1]), float(short[2]), float(short[3])

    if len(text) in (6, 8):
        long = [int(text[i : i + 2], 16) for i in range(0, len(text), 2)]
        if len(long) == 3:
            return float(long[0]), float(long[1]), float(long[2]), 255.0
        return float(long[0]), float(long[1]), float(long[2]), float(long[3])

    raise ValueError(f"Unsupported hex color: {value!r}, expected {sorted(_HEX_DIGITS)} digits")


def default_named_colors() -> dict[str, str]:
    """The css names ColorAide ships with, as hex strings.

    Snapshotted at import, before anything can replace the table, so this stays the pristine set no
    matter how many times the table is overwritten.

    Returns:
        dict[str, str]: Lowercase name to hex color, sorted by name.
    """
    return dict(sorted(_CSS_DEFAULTS.items()))


def load_named_colors(file: Path) -> dict[str, str]:
    """Reads a named color table, keeping only the entries ColorAide can use.

    Args:
        file (Path): The toml file to read.

    Returns:
        dict[str, str]: Lowercase name to hex color, sorted by name. Empty when the file is missing,
            unreadable, or holds nothing usable.
    """
    if not file.is_file():
        return {}

    try:
        data = tomllib.loads(file.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        logger.warning("Ignoring named colors from '%s': %s", file, e)
        return {}

    names: dict[str, str] = {}
    for key, value in data.items():  # pyright: ignore[reportAny]
        name = str(key).strip().lower()
        if name in RESERVED_NAMES:
            logger.warning("Ignoring named color '%s' in '%s', name is reserved.", name, file)
            continue
        try:
            _ = _from_hex(str(value))  # pyright: ignore[reportAny]
        except ValueError as e:
            logger.warning("Ignoring named color '%s' in '%s': %s", name, file, e)
            continue
        names[name] = str(value).strip().lower()  # pyright: ignore[reportAny]
    return dict(sorted(names.items()))


def save_named_colors(file: Path, names: dict[str, str]) -> None:
    """Writes a named color table as toml, creating the directory when needed.

    Args:
        file (Path): The toml file to write.
        names (dict[str, str]): Name to hex color.

    Raises:
        OSError: When the file cannot be written.
    """
    file.parent.mkdir(parents=True, exist_ok=True)
    _ = file.write_text(tomli_w.dumps(dict(sorted(names.items()))), encoding="utf-8")


def apply_named_colors(names: dict[str, str]) -> int:
    """Replaces ColorAide's name table outright and drops its tokenizer cache.

    Args:
        names (dict[str, str]): Name to hex color. Entries ColorAide cannot resolve are skipped, and
            the rest still replace the table rather than adding to it.

    Returns:
        int: How many names were actually installed.
    """
    vectors: dict[str, Channel4] = {}
    for name, value in names.items():
        try:
            vectors[name.strip().lower()] = _from_hex(value)
        except ValueError as e:
            logger.warning("Ignoring named color '%s': %s", name, e)

    # Assign in place rather than rebinding, because ColorAide's parser looks these up as
    # module globals. Clear first so a name dropped from the table stops resolving at all.
    _color_names.name2val_map.clear()
    for name, vector in vectors.items():
        _color_names.name2val_map[name] = vector

    _color_names.val2name_map.clear()
    for vector, name in ((v, k) for k, v in vectors.items()):
        _color_names.val2name_map[vector] = name

    tokenize_css.cache_clear()
    logger.debug("Installed %d named colors.", len(vectors))
    return len(vectors)


def ensure_named_colors_file(file: Path) -> dict[str, str]:
    """Seeds the file with the css defaults when absent, then returns what it holds.

    Args:
        file (Path): The toml file to seed and read.

    Returns:
        dict[str, str]: Lowercase name to hex color from the file.
    """
    names = load_named_colors(file)
    if not file.is_file():
        try:
            save_named_colors(file, default_named_colors())
        except OSError as e:
            logger.warning("Could not create named color file '%s': %s", file, e)
    return names or default_named_colors()


def named_color_names() -> list[str]:
    """Lists the names currently resolvable by ColorAide.

    Returns:
        list[str]: Installed names, sorted.
    """
    return sorted(_color_names.name2val_map)
