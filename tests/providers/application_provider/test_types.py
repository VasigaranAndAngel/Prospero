"""Tests for the environment given to launched applications."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

from providers.application_provider._types import Launch
from utils.env import child_environment


def test_child_environment_unchanged_when_not_frozen(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/some/user/path")

    assert child_environment() == dict(os.environ)


def test_child_environment_restores_original_library_path(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/opt/prospero/_internal")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/usr/lib")
    monkeypatch.setenv("_PYI_ARCHIVE_FILE", "/opt/prospero/Prospero")
    monkeypatch.setenv("_PYI_APPLICATION_HOME_DIR", "/opt/prospero/_internal")
    monkeypatch.setenv("PYINSTALLER_RESET_ENVIRONMENT", "0")
    monkeypatch.setenv("KEEP_ME", "yes")

    env = child_environment()

    assert env["LD_LIBRARY_PATH"] == "/usr/lib"
    assert env["KEEP_ME"] == "yes"
    assert "LD_LIBRARY_PATH_ORIG" not in env
    assert not any(key.startswith(("_PYI_", "PYINSTALLER_")) for key in env)


def test_child_environment_drops_library_path_without_original(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG", raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/opt/prospero/_internal")

    assert "LD_LIBRARY_PATH" not in child_environment()


def test_launch_passes_clean_environment(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/opt/prospero/_internal")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/usr/lib")
    monkeypatch.setenv("_PYI_ARCHIVE_FILE", "/opt/prospero/Prospero")

    with patch("providers.application_provider._types.subprocess.Popen") as popen:
        Launch(["/usr/bin/true"])()

    env = popen.call_args.kwargs["env"]
    assert env["LD_LIBRARY_PATH"] == "/usr/lib"
    assert "LD_LIBRARY_PATH_ORIG" not in env
    assert not any(key.startswith("_PYI_") for key in env)
