"""Tests for the Linux desktop entry discovery backend."""


from providers.application_provider.linux.apps import build_app_list, find_icon_file


def test_find_icon_file_resolves_theme_and_pixmaps(tmp_path, monkeypatch):
    # theme dir
    hicolor = tmp_path / "icons" / "hicolor" / "64x64" / "apps"
    hicolor.mkdir(parents=True)
    (hicolor / "foo.png").write_bytes(b"PNG")
    # pixmap
    pix = tmp_path / "pixmaps"
    pix.mkdir(parents=True)
    (pix / "bar.svg").write_text("<svg></svg>")

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path / "other"))

    assert find_icon_file("foo") == hicolor / "foo.png"
    assert find_icon_file("bar") == pix / "bar.svg"


def test_build_app_list_parses_exec_and_launch(tmp_path, monkeypatch):
    apps_dir = tmp_path / "applications"
    apps_dir.mkdir(parents=True)
    desk = apps_dir / "test.desktop"
    desk.write_text(
        """[Desktop Entry]
Name=Test App
Type=Application
Exec=/usr/bin/testapp %u
Icon=test
"""
    )
    hicolor = tmp_path / "icons" / "hicolor" / "64x64" / "apps"
    hicolor.mkdir(parents=True)
    (hicolor / "test.png").write_bytes(b"PNG")

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    apps = build_app_list()
    assert apps
    app = apps[0]
    assert app.app_name == "Test App"
    assert app.launch is not None
    assert app.launch.args == ["/usr/bin/testapp"]
    assert app.launch.shell is False
