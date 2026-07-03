import json

from ui import project_config


def test_save_and_load_project_headlessly(tmp_path, project_app):
    path = tmp_path / "roundtrip.simproject"

    assert project_config._write_project(project_app, path)
    with path.open(encoding="utf-8") as project_file:
        loaded = json.load(project_file)
    staged = project_config._stage_project_data(loaded)

    assert staged["format"] == project_config.PROJECT_FORMAT
    assert staged["plc"]["brand"] == "Siemens"
    assert [tag["name"] for tag in staged["tags"]] == ["Run", "Speed"]
    assert staged["tags"][1]["data_type"] == "REAL"


def test_corrupted_project_is_rejected(tmp_path, monkeypatch):
    path = tmp_path / "corrupt.simproject"
    path.write_text('{"format": broken json', encoding="utf-8")
    errors = []
    monkeypatch.setattr(
        project_config.filedialog,
        "askopenfilename",
        lambda **_kwargs: str(path),
    )
    monkeypatch.setattr(
        project_config.messagebox,
        "showerror",
        lambda title, message: errors.append((title, message)),
    )

    assert project_config.open_project(object()) is False
    assert errors
    assert "abrir projeto" in errors[0][0]


def test_modbus_tcp_project_connection_settings_round_trip(project_app):
    project_app.brand_menu.value = "Modbus TCP"
    project_app.port_entry = type(project_app.ip_entry)("1502")
    project_app.slave_entry = type(project_app.ip_entry)("7")

    project = project_config.build_project_data(project_app)
    staged = project_config._stage_project_data(project)

    assert staged["plc"] == {
        "brand": "Modbus TCP",
        "ip": "192.168.1.10",
        "settings": {"port": "1502", "slave_id": "7"},
    }
