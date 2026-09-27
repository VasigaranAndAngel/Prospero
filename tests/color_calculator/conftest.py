"""Fixtures for the color backend tests.

Every test that touches ColorAide's global name table has to put it back, because the
table is process wide and nothing else will.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from coloraide.css import color_names
from coloraide.css.parse import tokenize_css

from color_calculator import Color, apply_named_colors, default_named_colors


@pytest.fixture(autouse=True)
def restore_name_table() -> Iterator[None]:
    """Puts ColorAide's name table back after each test, so tests cannot leak into others."""
    saved = dict(color_names.name2val_map)
    saved_reverse = dict(color_names.val2name_map)
    try:
        yield
    finally:
        color_names.name2val_map.clear()
        color_names.name2val_map.update(saved)
        color_names.val2name_map.clear()
        color_names.val2name_map.update(saved_reverse)
        # The parsed name is cached, so a restored table with a stale cache would make the
        # next test read a color a previous one installed.
        tokenize_css.cache_clear()


@pytest.fixture
def named_colors_file(tmp_path: Path) -> Path:
    """A named color file that does not exist yet, so seeding can be observed."""
    return tmp_path / "color" / "named_colors.toml"


@pytest.fixture
def css_defaults_installed() -> None:
    """The full css table installed, the way a normal first run would leave it."""
    _ = apply_named_colors(default_named_colors())


@pytest.fixture
def red() -> Color:
    """A color for accessor tests that does not depend on any name being installed."""
    return Color("#336699")
