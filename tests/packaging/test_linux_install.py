"""End-to-end checks for the Linux install/uninstall script pair."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGING = REPO_ROOT / "packaging" / "linux"


def _stage(tmp_path: Path) -> dict[str, Path]:
    """Create a fake release archive root with deliberately spaced paths."""
    stage = tmp_path / "stage dir"
    app = stage / "Prospero"
    icon = app / "_internal" / "assets" / "icon" / "icon.png"
    icon.parent.mkdir(parents=True)
    (app / "Prospero").write_text("#!/bin/sh\nprintf '0.0.0.dev99\\n'\n")
    (app / "Prospero").chmod(0o755)
    icon.write_bytes(b"PNG")
    (stage / "VERSION").write_text("0.0.0.dev99\n")
    for name in ("install.sh", "uninstall.sh", "prospero.desktop"):
        (stage / name).write_bytes((PACKAGING / name).read_bytes())

    return {
        "stage": stage,
        "root": tmp_path / "install root",
        "bin": tmp_path / "bin dir",
        "data": tmp_path / "data dir",
        "home": tmp_path / "home dir",
    }


def _env(paths: dict[str, Path]) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "PROSPERO_INSTALL_ROOT": str(paths["root"]),
        "XDG_BIN_HOME": str(paths["bin"]),
        "XDG_DATA_HOME": str(paths["data"]),
        "HOME": str(paths["home"]),
    })
    return env


@pytest.fixture
def linux_install(tmp_path: Path) -> dict[str, Path]:
    paths = _stage(tmp_path)
    result = subprocess.run(
        ["bash", str(paths["stage"] / "install.sh")],
        cwd=paths["stage"],
        env=_env(paths),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return paths


def _write_user_files(paths: dict[str, Path]) -> tuple[Path, Path]:
    config = paths["home"] / ".config" / "Prospero" / "settings.toml"
    config.parent.mkdir(parents=True)
    config.write_text("theme = 'dark'\n")
    data = paths["data"] / "prospero" / "modules" / "example.txt"
    data.parent.mkdir(parents=True)
    data.write_text("module\n")
    return config, data


def test_install_creates_uninstaller_and_desktop_action(
    linux_install: dict[str, Path],
) -> None:
    root = linux_install["root"]
    uninstaller = root / "uninstall.sh"
    manifest = root / "install-paths.env"
    desktop = linux_install["data"] / "applications" / "prospero.desktop"
    icon = linux_install["data"] / "icons" / "hicolor" / "256x256" / "apps" / "prospero.png"

    assert uninstaller.is_file()
    assert os.access(uninstaller, os.X_OK)
    assert manifest.is_file()
    sourced = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; printf "%s\\n%s\\n%s\\n" '
            '"$PROSPERO_INSTALL_ROOT" "$PROSPERO_BIN_DIR" "$PROSPERO_DATA_DIR"',
            "bash",
            str(manifest),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert sourced == [
        str(root),
        str(linux_install["bin"]),
        str(linux_install["data"]),
    ]
    assert (linux_install["bin"] / "prospero").is_symlink()
    assert icon.is_file()

    text = desktop.read_text()
    assert "Actions=uninstall;" in text
    assert "[Desktop Action uninstall]" in text
    assert f'Exec="{uninstaller}" --gui' in text
    assert f'Exec="{linux_install["bin"] / "prospero"}"' in text
    assert "@EXEC@" not in text
    assert "@UNINSTALL@" not in text


def test_uninstall_keeps_user_data_by_default(linux_install: dict[str, Path]) -> None:
    config, data = _write_user_files(linux_install)
    root = linux_install["root"]
    uninstaller = root / "uninstall.sh"
    launcher = linux_install["bin"] / "prospero"
    desktop = linux_install["data"] / "applications" / "prospero.desktop"
    icon = linux_install["data"] / "icons" / "hicolor" / "256x256" / "apps" / "prospero.png"

    result = subprocess.run(
        [str(uninstaller), "--yes"],
        env=_env(linux_install),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    assert not root.exists()
    assert not launcher.is_symlink()
    assert not desktop.exists()
    assert not icon.exists()
    assert config.is_file()
    assert data.is_file()
    assert "kept" in result.stdout


def test_uninstall_purge_data(linux_install: dict[str, Path]) -> None:
    config, data = _write_user_files(linux_install)
    uninstaller = linux_install["root"] / "uninstall.sh"

    result = subprocess.run(
        [str(uninstaller), "--yes", "--purge-data"],
        env=_env(linux_install),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    assert not linux_install["root"].exists()
    assert not config.exists()
    assert not data.exists()
    assert "removed" in result.stdout
