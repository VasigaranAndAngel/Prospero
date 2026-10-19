"""Tests for the freedesktop (Linux) application provider.

Parsing helpers are pure and ``build_app_list`` reads its search paths from the XDG
environment variables at call time, so these tests stay hermetic (they point XDG at
``tmp_path``) and run on any platform.
"""

from pathlib import Path

import pytest

from data_objects import LoadMethod
from providers.application_provider._linux import build_app_list, find_icon_file


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(text, encoding="utf-8")


def _entry(
    *,
    name: str = "Test App",
    exec_line: str = "/usr/bin/testapp",
    icon: str = "",
    entry_type: str = "Application",
    **extra: str,
) -> str:
    lines = ["[Desktop Entry]", f"Type={entry_type}", f"Name={name}", f"Exec={exec_line}"]
    if icon:
        lines.append(f"Icon={icon}")
    lines.extend(f"{k}={v}" for k, v in extra.items())
    return "\n".join(lines) + "\n"


@pytest.fixture
def xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Point the XDG data directories at temporary folders."""
    data_home = tmp_path / "data"
    data_dirs = tmp_path / "sys"
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    monkeypatch.setenv("XDG_DATA_DIRS", str(data_dirs))
    return data_home, data_dirs


def test_entries_are_discovered(xdg: tuple[Path, Path]) -> None:
    data_home, _ = xdg
    _write(data_home / "applications" / "testapp.desktop", _entry(name="Test App"))

    apps = build_app_list()

    assert [a.app_name for a in apps] == ["Test App"]
    assert apps[0].type == "desktop"
    assert apps[0].exec_command == ["/usr/bin/testapp"]


def test_exec_field_codes_are_stripped(xdg: tuple[Path, Path]) -> None:
    data_home, _ = xdg
    _write(
        data_home / "applications" / "a.desktop",
        _entry(exec_line="/usr/bin/app --open %U %f --name %c"),
    )

    assert build_app_list()[0].exec_command == ["/usr/bin/app", "--open", "--name"]


def test_exec_escaped_percent_is_kept(xdg: tuple[Path, Path]) -> None:
    data_home, _ = xdg
    _write(data_home / "applications" / "a.desktop", _entry(exec_line="/usr/bin/app 100%%"))

    assert build_app_list()[0].exec_command == ["/usr/bin/app", "100%"]


def test_exec_quoted_argument_is_one_token(xdg: tuple[Path, Path]) -> None:
    data_home, _ = xdg
    _write(data_home / "applications" / "a.desktop", _entry(exec_line='"/opt/My App/app" --flag'))

    assert build_app_list()[0].exec_command == ["/opt/My App/app", "--flag"]


@pytest.mark.parametrize("extra", [{"NoDisplay": "true"}, {"Hidden": "true"}, {"Terminal": "true"}])
def test_hidden_and_terminal_entries_are_skipped(
    xdg: tuple[Path, Path], extra: dict[str, str]
) -> None:
    data_home, _ = xdg
    _write(data_home / "applications" / "skip.desktop", _entry(**extra))

    assert build_app_list() == []


def test_entry_without_exec_is_skipped(xdg: tuple[Path, Path]) -> None:
    data_home, _ = xdg
    _write(
        data_home / "applications" / "noexec.desktop",
        "[Desktop Entry]\nType=Application\nName=No Exec\n",
    )

    assert build_app_list() == []


def test_unsupported_type_is_skipped(xdg: tuple[Path, Path]) -> None:
    data_home, _ = xdg
    _write(data_home / "applications" / "dir.desktop", _entry(entry_type="Directory"))

    assert build_app_list() == []


def test_entry_without_desktop_section_is_skipped(xdg: tuple[Path, Path]) -> None:
    data_home, _ = xdg
    _write(data_home / "applications" / "other.desktop", "[Other]\nName=nope\n")

    assert build_app_list() == []


def test_user_entries_take_precedence_over_system(xdg: tuple[Path, Path]) -> None:
    data_home, data_dirs = xdg
    _write(data_home / "applications" / "dup.desktop", _entry(name="User Copy"))
    _write(data_dirs / "applications" / "dup.desktop", _entry(name="System Copy"))

    assert [a.app_name for a in build_app_list()] == ["User Copy"]


def test_icon_is_resolved_from_theme(xdg: tuple[Path, Path]) -> None:
    data_home, _ = xdg
    icon = data_home / "icons" / "hicolor" / "48x48" / "apps" / "prosperotest_theme.png"
    _write(icon, "placeholder")
    _write(data_home / "applications" / "b.desktop", _entry(icon="prosperotest_theme"))

    found = build_app_list()[0].icon

    assert found is not None
    assert found.load_method is LoadMethod.load_file
    assert found.file_path == icon


def test_icon_is_resolved_from_pixmaps(xdg: tuple[Path, Path]) -> None:
    _, data_dirs = xdg
    icon = data_dirs / "pixmaps" / "prosperotest_pixmap.png"
    _write(icon, "placeholder")

    assert find_icon_file("prosperotest_pixmap") == icon


def test_absolute_icon_path_is_used(xdg: tuple[Path, Path], tmp_path: Path) -> None:
    data_home, _ = xdg
    icon = tmp_path / "custom.svg"
    _write(icon, "<svg/>")
    _write(data_home / "applications" / "c.desktop", _entry(icon=str(icon)))

    assert build_app_list()[0].icon.file_path == icon


def test_icon_defaults_when_not_found(xdg: tuple[Path, Path]) -> None:
    data_home, _ = xdg
    _write(data_home / "applications" / "d.desktop", _entry(icon="prosperotest_absent_icon"))

    found = build_app_list()[0].icon

    assert found is not None
    assert found.load_method is LoadMethod.default


def test_find_icon_file_returns_none_for_unknown_name(xdg: tuple[Path, Path]) -> None:
    assert find_icon_file("prosperotest_totally_absent") is None
