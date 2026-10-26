"""Tests for the Linux desktop entry discovery backend."""

from providers.application_provider.linux.apps import build_app_list


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
