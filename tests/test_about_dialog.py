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


def _isolated_version_import(tmp_path, generated_metadata=None):
    project_root = Path(__file__).parent.parent
    core_dir = tmp_path / "core"
    core_dir.mkdir()
    (core_dir / "__init__.py").write_text("", encoding="utf-8")
    (core_dir / "version.py").write_text(
        (project_root / "core" / "version.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    if generated_metadata is not None:
        generated_dir = core_dir / "generated"
        generated_dir.mkdir()
        (generated_dir / "build_metadata.py").write_text(
            generated_metadata,
            encoding="utf-8",
        )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import core.version as v; print('|'.join((v.APP_VERSION, v.APP_RELEASE, v.APP_GIT_COMMIT, v.APP_GIT_BRANCH, v.APP_BUILD_DATE)))",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_core_version_falls_back_without_generated_metadata(tmp_path):
    values = _isolated_version_import(tmp_path)

    assert values == "2.2.5-rc1+2.g370c8be|Development|370c8be|main|2026-07-17 08:54 UTC"


def test_core_version_prefers_generated_metadata(tmp_path):
    values = _isolated_version_import(
        tmp_path,
        "APP_VERSION = '9.8.7'\n"
        "APP_RELEASE = 'Stable'\n"
        "APP_GIT_COMMIT = 'abc1234'\n"
        "APP_GIT_BRANCH = 'release'\n"
        "APP_BUILD_DATE = '2026-01-02 03:04 UTC'\n",
    )

    assert values == "9.8.7|Stable|abc1234|release|2026-01-02 03:04 UTC"
