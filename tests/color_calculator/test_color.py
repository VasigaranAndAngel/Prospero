"""Tests for the Color type: the byte and HSV accessors, and the Qt interop methods."""

import math

import pytest
from PySide6.QtGui import QColor

from color_calculator import Color

# region channel accessors


def test_channels_come_back_as_bytes(red: Color) -> None:
    assert (red.red(), red.green(), red.blue()) == (51, 102, 153)


def test_hsv_accessors_match_an_independent_implementation() -> None:
    # Cross checked against an independent HSV implementation.
    for hexed in ("#336699", "#ff0000", "#00ff00", "#0000ff", "#808080", "#f0f8ff"):
        color = Color(hexed)
        q = QColor(hexed)
        assert (color.hue(), color.saturation(), color.value()) == (
            q.hue(),
            q.saturation(),
            q.value(),
        ), hexed


def test_hsv_wraps_into_a_single_turn() -> None:
    assert Color("hsl(0 100% 50%)").hue() == 0
    assert 0 <= Color("hsl(359 100% 50%)").hue() <= 359


def test_alpha_is_left_to_coloraide(red: Color) -> None:
    """ColorAide already has alpha(); it must not be shadowed by a byte flavoured one."""
    assert red.alpha() == 1.0
    assert not hasattr(red, "alpha_byte")


def test_out_of_gamut_channels_stay_in_byte_range() -> None:
    """A wide gamut color has to survive being reduced to 8 bit channels."""
    wide = Color("color(display-p3 1 0 0)")

    for channel in (wide.red(), wide.green(), wide.blue()):
        assert 0 <= channel <= 255

    q = wide.to_qcolor()
    assert (q.red(), q.green(), q.blue()) == (wide.red(), wide.green(), wide.blue())


def test_achromatic_colors_report_a_hue_instead_of_failing() -> None:
    """HSV hue is NaN for a grey, which is reported as -1 rather than raising."""
    grey = Color("#808080")
    assert grey.saturation() == 0
    assert grey.hue() == -1
    assert QColor("#808080").hue() == -1


# endregion

# region validity


def test_an_ordinary_color_is_valid(red: Color) -> None:
    assert red.is_valid() is True


def test_a_nan_channel_is_not_valid() -> None:
    assert Color("rgb(none 0 0)").is_valid() is False
    assert math.isnan(Color("rgb(none 0 0)")[0])


def test_transparent_is_still_valid() -> None:
    assert Color("transparent").is_valid() is True


# endregion

# region naming


@pytest.mark.usefixtures("css_defaults_installed")
def test_a_color_can_report_its_name() -> None:
    assert Color("red").name() == "red"
    assert Color("#ff0000").name() == "red"


@pytest.mark.usefixtures("css_defaults_installed")
def test_a_color_with_no_name_says_so() -> None:
    assert Color("#010203").name() is None


@pytest.mark.usefixtures("css_defaults_installed")
def test_naming_works_from_another_space() -> None:
    """The lookup goes through sRGB, so a color named from Lab still finds its name."""
    assert Color("lab(54.29 80.8 69.9)").name() == "red"


# endregion

# region qt interop


def test_to_qcolor_clips_to_srgb(red: Color) -> None:
    q = red.to_qcolor()
    assert (q.red(), q.green(), q.blue(), q.alpha()) == (51, 102, 153, 255)


def test_to_qcolor_keeps_alpha() -> None:
    assert Color("#336699").set("alpha", 0.5).to_qcolor().alpha() == 128


def test_a_qcolor_round_trips(red: Color) -> None:
    assert Color.from_qcolor(red.to_qcolor()).coords() == pytest.approx(red.coords())


def test_a_qcolor_round_trips_alpha() -> None:
    """A round trip that drops alpha would still pass a coords only comparison."""
    original = Color("#336699").set("alpha", 0.5)
    # QColor holds alpha in one byte, so allow that much rounding.
    assert Color.from_qcolor(original.to_qcolor()).alpha() == pytest.approx(0.5, abs=1 / 255)


def test_from_qcolor_accepts_an_invalid_qcolor() -> None:
    """An unparsable string gives an invalid QColor, which must not raise here."""
    color = Color.from_qcolor(QColor("not a color"))
    assert color.is_valid() is False


def test_qt_is_only_imported_on_demand() -> None:
    """The module has to stay importable with no Qt around, so the import is local."""
    import subprocess
    import sys

    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, 'src');"
            + " import color_calculator;"
            + " print(any(m.startswith('PySide6') for m in sys.modules))",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "False", result.stderr


# endregion
