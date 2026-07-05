from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent


def test_linux_desktop_integration_files_exist():
    assert (PROJECT_ROOT / "assets" / "icon.png").is_file()
    assert (
        PROJECT_ROOT
        / "packaging"
        / "linux"
        / "plc-universal-simulator.desktop"
    ).is_file()
    assert (PROJECT_ROOT / "scripts" / "install_linux.sh").is_file()
    assert (PROJECT_ROOT / "scripts" / "uninstall_linux.sh").is_file()
