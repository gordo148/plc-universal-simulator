from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).parent.parent


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


def test_windows_icon_contains_required_resolutions():
    with Image.open(PROJECT_ROOT / "assets" / "icon.ico") as icon:
        assert icon.ico.sizes() == {
            (16, 16),
            (32, 32),
            (48, 48),
            (256, 256),
        }
