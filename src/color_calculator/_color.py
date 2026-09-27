"""
A ColorAide color with byte and HSV accessors, plus our named color table.

Only conveniences ColorAide does not already provide are added. Anything ColorAide owns stays
reachable as ColorAide defines it, so nothing here shadows or reinterprets an existing method.
"""

import math
from typing import TYPE_CHECKING

from coloraide import Color as _ColorAideColor
from coloraide import algebra as alg

from ._named_colors import _color_names

if TYPE_CHECKING:  # pragma: no cover
    from PySide6.QtGui import QColor

_BYTE_MAX: int = 255


def _byte(value: float) -> int:
    """Rounds a 0-1 channel to a 0-255 byte.

    Out of range values clip, and a channel that has no value reads as 0.

    Args:
        value (float): Channel value, nominally 0-1 but possibly outside it or NaN.

    Returns:
        int: The nearest byte.
    """
    if math.isnan(value):
        return 0
    return int(alg.round_half_up(max(0.0, min(1.0, value)) * _BYTE_MAX))


class Color(_ColorAideColor):
    """A color, with byte and HSV accessors and ColorAide's engine underneath."""

    def red(self) -> int:
        """Red channel as a byte, in sRGB."""
        return _byte(self.convert("srgb")["red"])

    def green(self) -> int:
        """Green channel as a byte, in sRGB."""
        return _byte(self.convert("srgb")["green"])

    def blue(self) -> int:
        """Blue channel as a byte, in sRGB."""
        return _byte(self.convert("srgb")["blue"])

    def hue(self) -> int:
        """Hue in degrees, taken from HSV.

        An achromatic color has no hue, so it is reported as -1 rather than raising. The other
        two HSV accessors return a byte, and none of them fail on a missing channel.
        """
        hue = self.convert("hsv")["hue"]
        return -1 if math.isnan(hue) else int(alg.round_half_up(hue)) % 360

    def saturation(self) -> int:
        """HSV saturation as a byte, 0 to 255. Not HSL saturation."""
        return _byte(self.convert("hsv")["saturation"])

    def value(self) -> int:
        """HSV value as a byte, 0 to 255. Not HSL lightness."""
        return _byte(self.convert("hsv")["value"])

    def is_valid(self) -> bool:
        """Whether every channel is a real number.

        A color built from ``none`` or from a malformed input has NaN channels, which most
        arithmetic on it will propagate.

        Returns:
            bool: True when no channel is NaN.
        """
        return not any(math.isnan(c) for c in (*self.coords(), self.alpha()))

    def name(self) -> str | None:
        """The named color matching this one exactly, if the table holds one.

        Round trips through sRGB, so a color in another space is matched on its sRGB value. The
        table is many to one, so colors sharing a value can only report one of their names.

        Returns:
            str | None: The name, or None when no name matches.
        """
        return _color_names.to_name(list(self.convert("srgb")[:]))

    def to_qcolor(self) -> "QColor":
        """Converts to a QColor, clipping to the sRGB gamut.

        QColor stores 8 bit sRGB only, so a wider gamut color is reduced rather than rejected.

        Returns:
            QColor: The equivalent color, with alpha as a byte.
        """
        from PySide6.QtGui import QColor

        srgb = self.convert("srgb")
        return QColor.fromRgb(self.red(), self.green(), self.blue(), _byte(srgb["alpha"]))

    @classmethod
    def from_qcolor(cls, color: "QColor") -> "Color":
        """Builds a color from a QColor.

        Args:
            color (QColor): The color to read. An invalid QColor, which is what an unparsable
                string produces, becomes a color with NaN channels rather than silently becoming
                black.

        Returns:
            Color: The equivalent color.
        """
        if not color.isValid():
            return cls("srgb", [math.nan, math.nan, math.nan])
        # ColorAide's constructor ignores an alpha keyword for a css string, so the alpha has to be
        # set afterwards or it is silently lost.
        return cls(f"rgb({color.red()}, {color.green()}, {color.blue()})").set(
            "alpha", color.alpha() / 255
        )


__all__ = ["Color"]
