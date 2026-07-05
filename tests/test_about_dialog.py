from ui.main_window import get_about_text


def test_about_text_contains_release_and_runtime_information():
    about = get_about_text()

    assert "PLC Universal Simulator" in about
    assert "Version: v2.2 Stable" in about
    assert "Build type:" in about
    assert "Python:" in about
    assert "Operating system:" in about
    assert "Siemens S7" in about
    assert "Schneider Modbus TCP" in about
    assert "Generic Modbus TCP" in about
    assert "Rockwell EtherNet/IP" in about
    assert "Omron FINS" in about
    assert "Internal Simulator" in about
    assert "Plugin support:" in about
