import sys
import subprocess
from pathlib import Path

from core.version import (
    APP_BUILD_DATE,
    APP_GIT_BRANCH,
    APP_GIT_COMMIT,
    APP_NAME,
    APP_RELEASE,
    APP_VERSION,
    get_build_type,
)
from ui.main_window import get_about_text


def test_about_text_contains_release_and_runtime_information():
    about = get_about_text()

    assert APP_NAME in about
    assert f"Version: {APP_VERSION}" in about
    assert f"Release: {APP_RELEASE}" in about
    assert f"Build: {get_build_type()}" in about
    assert f"Commit: {APP_GIT_COMMIT}" in about
    assert f"Branch: {APP_GIT_BRANCH}" in about
    assert f"Built on: {APP_BUILD_DATE}" in about
    assert "Python:" in about
    assert "Operating system:" in about
    assert "Siemens S7" in about
    assert "Schneider Modbus TCP" in about
    assert "Generic Modbus TCP" in about
    assert "Rockwell EtherNet/IP" in about
    assert "Omron FINS" in about
    assert "Internal Simulator" in about
    assert "Plugin support:" in about


def test_about_text_detects_packaged_build(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    assert "Build: Packaged desktop build" in get_about_text()


def test_core_version_falls_back_without_generated_metadata():
    project_root = Path(__file__).parent.parent
    result = subprocess.run(
        [sys.executable, "-c", "import core.version as v; print(v.APP_VERSION)"],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip()
