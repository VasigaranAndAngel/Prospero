"""Tests for the named color table and how it overrides ColorAide's own."""

from pathlib import Path

import pytest

from color_calculator import (
    Color,
    apply_named_colors,
    apply_settings,
    default_named_colors,
    ensure_named_colors_file,
    load_color_settings,
    load_named_colors,
    named_color_names,
    save_named_colors,
)
from color_calculator._named_colors import _from_hex, _to_hex  # pyright: ignore[reportPrivateUsage]

# region hex conversion


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("#f0f8ff", (240.0, 248.0, 255.0, 255.0)),
        ("#abc", (170.0, 187.0, 204.0, 255.0)),
        ("#abcd", (170.0, 187.0, 204.0, 221.0)),
        ("0000ff", (0.0, 0.0, 255.0, 255.0)),
        ("#00ff0080", (0.0, 255.0, 0.0, 128.0)),
        ("  #FFF  ", (255.0, 255.0, 255.0, 255.0)),
    ],
)
def test_hex_parsing_covers_every_accepted_form(value: str, expected: tuple[float, ...]) -> None:
    assert _from_hex(value) == expected


@pytest.mark.parametrize("value", ["", "#", "#ff", "#12345", "#gg0000", "rgb(0,0,0)"])
def test_bad_hex_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        _ = _from_hex(value)


def test_hex_round_trips_through_both_directions() -> None:
    """Every default has to survive being written to a file and read back."""
    for name, hexed in default_named_colors().items():
        assert _to_hex(_from_hex(hexed)) == hexed, name


def test_alpha_is_only_written_when_it_is_not_opaque() -> None:
    assert _to_hex((1.0, 2.0, 3.0, 255.0)) == "#010203"
    assert _to_hex((1.0, 2.0, 3.0, 0.0)) == "#01020300"


# endregion

# region file handling


def test_a_missing_file_yields_no_names(named_colors_file: Path) -> None:
    assert load_named_colors(named_colors_file) == {}


def test_seeding_writes_the_css_defaults(named_colors_file: Path) -> None:
    names = ensure_named_colors_file(named_colors_file)

    assert named_colors_file.is_file()
    assert names == default_named_colors()
    assert 'aliceblue = "#f0f8ff"' in named_colors_file.read_text(encoding="utf-8")


def test_seeding_leaves_an_existing_file_alone(tmp_path: Path) -> None:
    file = tmp_path / "named_colors.toml"
    save_named_colors(file, {"brand": "#112233"})

    assert ensure_named_colors_file(file) == {"brand": "#112233"}
    assert file.read_text(encoding="utf-8").strip() == 'brand = "#112233"'


def test_a_saved_table_survives_a_reload(tmp_path: Path) -> None:
    file = tmp_path / "named_colors.toml"
    names = default_named_colors()
    save_named_colors(file, names)

    assert load_named_colors(file) == names


def test_an_unreadable_file_is_ignored(tmp_path: Path) -> None:
    file = tmp_path / "named_colors.toml"
    _ = file.write_text("this is not = valid = toml", encoding="utf-8")

    assert load_named_colors(file) == {}


def test_unusable_entries_are_skipped_and_the_rest_kept(tmp_path: Path) -> None:
    file = tmp_path / "named_colors.toml"
    _ = file.write_text(
        'good = "#010203"\nbad = "not-a-color"\nalso_good = "#040506"\n', encoding="utf-8"
    )

    assert load_named_colors(file) == {"also_good": "#040506", "good": "#010203"}


def test_reserved_names_are_dropped(tmp_path: Path) -> None:
    """A name ColorAide matches as a function could never be reached, so it is refused."""
    file = tmp_path / "named_colors.toml"
    _ = file.write_text('rgb = "#010203"\nnone = "#040506"\nbrand = "#070809"\n')

    assert load_named_colors(file) == {"brand": "#070809"}


# endregion

# region applying


def test_applying_replaces_the_table_outright() -> None:
    """A dropped name has to stop resolving, otherwise the file is additive by accident."""
    _ = apply_named_colors({"brand": "#112233"})

    assert named_color_names() == ["brand"]
    with pytest.raises(ValueError):
        _ = Color("aliceblue")


def test_applying_ignores_entries_it_cannot_parse() -> None:
    installed = apply_named_colors({"brand": "#112233", "broken": "nonsense"})

    assert installed == 1
    assert named_color_names() == ["brand"]


@pytest.mark.usefixtures("css_defaults_installed")
def test_appplied_names_parse_through_color() -> None:
    assert Color("aliceblue").to_dict() == {
        "space": "srgb",
        "coords": [240 / 255, 248 / 255, 255 / 255],
        "alpha": 1.0,
    }


@pytest.mark.usefixtures("css_defaults_installed")
def test_transparent_keeps_its_alpha() -> None:
    assert Color("transparent").alpha() == 0.0


def test_the_tokenizer_cache_is_cleared_so_edits_take_effect() -> None:
    """Parsing a name caches the answer, so a replacement has to invalidate that."""
    _ = apply_named_colors({"brand": "#112233"})
    assert Color("brand").to_dict()["coords"][0] == pytest.approx(17 / 255)

    _ = apply_named_colors({"brand": "#ff0000"})
    assert Color("brand").to_dict()["coords"][0] == pytest.approx(1.0)


def test_reverse_lookup_is_rebuilt_too() -> None:
    """A stale reverse map would report a name for a color that no longer holds it."""
    _ = apply_named_colors({"brand": "#112233"})
    assert Color("brand").name() == "brand"

    _ = apply_named_colors({"other": "#445566"})
    assert Color("#112233").name() is None


def test_the_pristine_defaults_are_not_affected_by_replacement() -> None:
    before = default_named_colors()
    _ = apply_named_colors({"brand": "#112233"})

    assert default_named_colors() == before


# endregion

# region settings wiring


def test_settings_default_to_the_standard_location() -> None:
    assert str(load_color_settings(Path("missing.toml")).general.named_colors_file.value).endswith(
        ("color" + "\\" + "named_colors.toml", "color/named_colors.toml")
    )


def test_apply_settings_seeds_from_the_configured_file(named_colors_file: Path) -> None:
    settings = load_color_settings()
    settings.general.named_colors_file.value = str(named_colors_file)

    names = apply_settings(settings)

    assert named_colors_file.is_file()
    assert names == default_named_colors()
    assert len(named_color_names()) == len(names)


def test_apply_settings_installs_a_custom_table(named_colors_file: Path) -> None:
    named_colors_file.parent.mkdir(parents=True, exist_ok=True)
    _ = named_colors_file.write_text('brand = "#112233"\n', encoding="utf-8")
    settings = load_color_settings()
    settings.general.named_colors_file.value = str(named_colors_file)

    _ = apply_settings(settings)

    assert named_color_names() == ["brand"]
    assert Color("brand").to_dict()["coords"][0] == pytest.approx(17 / 255)


def test_settings_round_trip_through_their_own_file(tmp_path: Path) -> None:
    file = tmp_path / "color.toml"
    settings = load_color_settings()
    settings.general.named_colors_file.value = "somewhere/else.toml"
    settings.save(file)

    reloaded = load_color_settings(file)

    assert reloaded.general.named_colors_file.value == "somewhere/else.toml"
    assert reloaded.source() == file


def test_unreadable_settings_fall_back_to_defaults(tmp_path: Path) -> None:
    file = tmp_path / "color.toml"
    _ = file.write_text("= broken", encoding="utf-8")

    settings = load_color_settings(file)

    assert (
        settings.general.named_colors_file.value
        == load_color_settings(Path("missing.toml")).general.named_colors_file.value
    )
    assert settings.source() is None


def test_settings_that_do_not_validate_fall_back_to_defaults(tmp_path: Path) -> None:
    file = tmp_path / "color.toml"
    _ = file.write_text("[general]\nnamed_colors_file = 42\n", encoding="utf-8")

    assert load_color_settings(file).source() is None


# endregion
