"""Tests for the allowlist that decides what may be installed and from where."""

import dataclasses

import pytest
from packaging.tags import Tag
from packaging.version import Version

from package_manager import (
    ALLOWLIST,
    AllowedWheel,
    PackageError,
    allowed_import_names,
    get_allowed,
    select_wheel,
)
from package_manager._allowlist import PILLOW

OTHER_PLATFORM: frozenset[Tag] = frozenset({Tag("cp999", "cp999", "nonesuch_platform")})


def test_known_package_resolves_by_distribution_name() -> None:
    assert get_allowed("pillow") is PILLOW


def test_resolution_is_case_and_separator_insensitive() -> None:
    assert get_allowed("Pillow") is PILLOW
    assert get_allowed("PIL") is PILLOW


def test_unknown_package_is_refused() -> None:
    with pytest.raises(PackageError) as e:
        _ = get_allowed("requests")

    assert "not an installable module" in e.value.error_str
    assert "pillow" in e.value.error_str


def test_allowlist_contains_pillow() -> None:
    assert "pillow" in ALLOWLIST
    assert allowed_import_names() == ("PIL",)


# region wheel selection


def test_current_interpreter_gets_a_wheel() -> None:
    assert select_wheel(PILLOW) is not None


def test_matching_interpreter_gets_the_pinned_wheel() -> None:
    tags = frozenset({Tag("cp312", "cp312", "win_amd64")})

    selected = select_wheel(PILLOW, tags)

    assert selected is not None
    assert selected.filename == "pillow-12.3.0-cp312-cp312-win_amd64.whl"


def test_foreign_platform_gets_nothing() -> None:
    assert select_wheel(PILLOW, OTHER_PLATFORM) is None


def test_version_tag_must_also_match() -> None:
    tags = frozenset({Tag("cp313", "cp313", "win_amd64")})

    assert select_wheel(PILLOW, tags) is None


def test_requires_python_is_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pin whose requires_python excludes the pinned version is not selectable."""
    monkeypatch.setitem(
        PILLOW.wheels,
        "win_amd64",
        dataclasses.replace(PILLOW.wheels["win_amd64"], requires_python="<1"),
    )

    tags = frozenset({Tag("cp312", "cp312", "win_amd64")})

    assert select_wheel(PILLOW, tags) is None


# endregion


# region derived values


def test_canonical_name_is_normalised() -> None:
    assert Version(PILLOW.version) == Version("12.3.0")
    assert PILLOW.canonical_name == "pillow"


def test_dist_info_matches_what_the_wheel_creates() -> None:
    assert PILLOW.dist_info == "pillow-12.3.0.dist-info"


def test_allowed_top_level_covers_import_name_and_metadata() -> None:
    assert PILLOW.allowed_top_level == frozenset({"PIL", "pillow-12.3.0.dist-info"})


def test_wheel_tags_are_read_from_the_filename() -> None:
    assert Tag("cp312", "cp312", "win_amd64") in PILLOW.wheels["win_amd64"].platform_tags


def test_pinned_digest_is_a_full_sha256() -> None:
    digest = PILLOW.wheels["win_amd64"].sha256

    assert len(digest) == 64
    assert set(digest) <= set("0123456789abcdef")


def test_malformed_wheel_filename_yields_no_tags() -> None:
    wheel = AllowedWheel(filename="nonsense", sha256="", size=0, url="")

    assert wheel.platform_tags == frozenset()


# endregion
