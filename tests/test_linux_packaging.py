from pathlib import Path
import sys

from PIL import Image

from core.application_identity import (
    APPLICATION_ID,
    DESKTOP_FILE_NAME,
)
from core.version import APP_NAME
from ui.main_window import get_application_icon_path


PROJECT_ROOT = Path(__file__).parent.parent


def _desktop_values():
    desktop_file = (
        PROJECT_ROOT / "packaging" / "linux" / DESKTOP_FILE_NAME
    )
    return dict(
        line.split("=", 1)
        for line in desktop_file.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )


def test_desktop_integration_files_exist():
    assert (PROJECT_ROOT / "assets" / "icon.png").is_file()
    assert (PROJECT_ROOT / "assets" / "icon.ico").is_file()
    assert (
        PROJECT_ROOT
        / "packaging"
        / "linux"
        / "plc-universal-simulator.desktop"
    ).is_file()
    assert (PROJECT_ROOT / "scripts" / "install_linux.sh").is_file()
    assert (PROJECT_ROOT / "scripts" / "uninstall_linux.sh").is_file()
    assert (PROJECT_ROOT / "scripts" / "build_windows.bat").is_file()
    assert (PROJECT_ROOT / "scripts" / "install_windows.bat").is_file()
    assert (PROJECT_ROOT / "scripts" / "uninstall_windows.bat").is_file()


def test_pyinstaller_includes_generated_build_metadata():
    spec = (PROJECT_ROOT / "plc-universal-simulator.spec").read_text(encoding="utf-8")

    assert '"core.generated.build_metadata"' in spec


def test_build_scripts_generate_metadata_before_pyinstaller():
    linux = (PROJECT_ROOT / "scripts" / "build_linux.sh").read_text(encoding="utf-8")
    windows = (PROJECT_ROOT / "scripts" / "build_windows.bat").read_text(encoding="utf-8")

    assert linux.index("scripts/generate_version.py") < linux.index("-m PyInstaller")
    assert windows.index(r"scripts\generate_version.py") < windows.index("-m PyInstaller")
    assert "core/version.py" not in linux
    assert "core\\version.py" not in windows


def test_windows_icon_contains_required_resolutions():
    with Image.open(PROJECT_ROOT / "assets" / "icon.ico") as icon:
        assert icon.ico.sizes() == {
            (16, 16),
            (32, 32),
            (48, 48),
            (256, 256),
        }


def test_canonical_application_identity():
    assert APPLICATION_ID == "plc-universal-simulator"
    assert DESKTOP_FILE_NAME == "plc-universal-simulator.desktop"
    assert APP_NAME == "PLC Universal Simulator"


def test_tk_root_is_created_with_canonical_class():
    main_window = (PROJECT_ROOT / "ui" / "main_window.py").read_text(
        encoding="utf-8"
    )

    assert "ctk.CTk(className=APPLICATION_ID)" in main_window


def test_desktop_file_uses_canonical_window_identity():
    desktop = _desktop_values()

    assert desktop["Name"] == APP_NAME
    assert desktop["Exec"] == APPLICATION_ID
    assert desktop["Icon"] == APPLICATION_ID
    assert desktop["StartupWMClass"] == APPLICATION_ID


def test_installer_writes_canonical_desktop_metadata_and_hicolor_icon():
    installer = (PROJECT_ROOT / "scripts" / "install_linux.sh").read_text(
        encoding="utf-8"
    )

    assert 'ICON_THEME_DIR="${HOME}/.local/share/icons/hicolor"' in installer
    assert 'ICON_DIR="${ICON_THEME_DIR}/256x256/apps"' in installer
    assert '"${DESKTOP_DIR}/plc-universal-simulator.desktop"' in installer
    assert '"${ICON_DIR}/plc-universal-simulator.png"' in installer
    assert 'LEGACY_ICON="${HOME}/.local/share/icons/plc-universal-simulator.png"' in installer
    assert 'rm -f -- "${LEGACY_ICON}"' in installer
    assert "gtk-update-icon-cache" in installer
    assert "update-desktop-database" in installer


def test_source_application_icon_uses_absolute_packaged_asset_path():
    icon_path = get_application_icon_path()

    assert icon_path == (PROJECT_ROOT / "assets" / "icon.png").resolve()
    assert icon_path.is_absolute()


def test_packaged_application_icon_uses_pyinstaller_bundle(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    icon_path = get_application_icon_path()

    assert icon_path == (tmp_path / "assets" / "icon.png").resolve()
    assert icon_path.is_absolute()
