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

    def contrast_ratio(self, other: "Color") -> float:
        """Returns WCAG contrast ratio between this and another color.

        Uses ColorAide's contrast calculation (1.0..21.0 for sRGB).

        Args:
            other (Color): The color to compare against.

        Returns:
            float: Contrast ratio.
        """
        return float(self.contrast(other))

    def relative_luminance(self) -> float:
        """Relative luminance (WCAG) for this color.

        Returns:
            float: Luminance value (0.0=black, ~1.0=white).
        """
        return float(self.luminance())

    def text_color(self, candidates: tuple["Color", ...] | None = None) -> "Color":
        """Returns the best contrasting text color from candidates against this background.

        Defaults to white and black. Chooses the candidate with highest contrast ratio.

        Args:
            candidates (tuple[Color, ...] | None): Candidate text colors. Defaults to (white, black).

        Returns:
            Color: The candidate with highest contrast.
        """
        if candidates is None:
            candidates = (Color("white"), Color("black"))

        best = candidates[0]
        best_ratio = float(self.contrast(best))
        for c in candidates[1:]:
            ratio = float(self.contrast(c))
            if ratio > best_ratio:
                best_ratio = ratio
                best = c
        return best

    def is_readable(self, other: "Color", level: str = "AA", size: str = "body") -> bool:
        """Check WCAG readability between this and another color.

        Args:
            other (Color): The other color (usually foreground against background; order doesn't affect threshold check by value).
            level (str): "AA" or "AAA".
            size (str): "body" or "large" (affects thresholds).

        Returns:
            bool: True if contrast meets WCAG threshold.
        """
        ratio = float(self.contrast(other))
        level_norm = level.upper()
        size_norm = size.lower()

        if level_norm == "AA":
            if size_norm == "large":
                return ratio >= 3.0
            return ratio >= 4.5
        if level_norm == "AAA":
            if size_norm == "large":
                return ratio >= 4.5
            return ratio >= 7.0
        return ratio >= 4.5

    def delta_e2000(self, other: "Color") -> float:
        """Delta E (CIEDE2000) distance to another color.

        Returns:
            float: Delta E 2000 value.
        """
        return float(self.delta_e(other, method="2000"))

    def lighten(self, amount: float = 0.1) -> "Color":
        """Lighten color by increasing HSL lightness.

        Args:
            amount (float): Amount to increase lightness (0..1). Defaults to 0.1.

        Returns:
            Color: Lightened color.
        """
        hsl = self.convert("hsl")
        new_l = max(0.0, min(1.0, float(hsl["lightness"]) + amount))
        return hsl.set("lightness", new_l).convert("srgb")

    def darken(self, amount: float = 0.1) -> "Color":
        """Darken color by decreasing HSL lightness.

        Args:
            amount (float): Amount to decrease lightness (0..1). Defaults to 0.1.

        Returns:
            Color: Darkened color.
        """
        return self.lighten(-amount)

    def saturate(self, amount: float = 0.1) -> "Color":
        """Increase saturation in HSL.

        Args:
            amount (float): Amount to increase saturation (0..1). Defaults to 0.1.

        Returns:
            Color: Saturated color.
        """
        hsl = self.convert("hsl")
        new_s = max(0.0, min(1.0, float(hsl["saturation"]) + amount))
        return hsl.set("saturation", new_s).convert("srgb")

    def desaturate(self, amount: float = 0.1) -> "Color":
        """Decrease saturation in HSL.

        Args:
            amount (float): Amount to decrease saturation (0..1). Defaults to 0.1.

        Returns:
            Color: Desaturated color.
        """
        return self.saturate(-amount)

    def tint(self, amount: float = 0.1) -> "Color":
        """Tint by mixing with white."""
        return self.mix(Color("white"), amount).convert("srgb")

    def shade(self, amount: float = 0.1) -> "Color":
        """Shade by mixing with black."""
        return self.mix(Color("black"), amount).convert("srgb")

    def spin(self, degrees: float) -> "Color":
        """Rotate hue by degrees (0-360)."""
        hsl = self.convert("hsl")
        hue = float(hsl["hue"])
        if math.isnan(hue):
            hue = 0.0
        hue = (hue + degrees) % 360.0
        return hsl.set("hue", hue).convert("srgb")

    def complementary(self) -> tuple["Color", ...]:
        """Complementary color (180 degrees)."""
        return (self, self.spin(180.0))

    def triadic(self) -> tuple["Color", ...]:
        """Triadic colors (120° apart)."""
        return (self, self.spin(120.0), self.spin(240.0))

    def tetradic(self) -> tuple["Color", ...]:
        """Tetradic (square) colors."""
        return (self, self.spin(90.0), self.spin(180.0), self.spin(270.0))

    def split_complementary(self) -> tuple["Color", ...]:
        """Split complementary (this + 150° + 210°)."""
        return (self, self.spin(150.0), self.spin(210.0))

    def analogous(self, count: int = 3, step: float = 30.0) -> tuple["Color", ...]:
        """Analogous colors around this hue."""
        count = max(1, int(count))
        half = (count - 1) // 2
        result: list["Color"] = []
        for i in range(-half, count - half):
            result.append(self.spin(i * step))
        return tuple(result)

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
