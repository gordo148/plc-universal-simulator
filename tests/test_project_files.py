import json

from core.tag_model import TagDefinition
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


def test_5000_tags_are_serialized_and_written_once(tmp_path, project_app, monkeypatch):
    project_app.tags = [
        TagDefinition(f"T{i}", "BOOL", "Input", f"DBX{i // 8}.{i % 8}")
        for i in range(5000)
    ]
    calls = []
    original_dump = project_config.json.dump
    monkeypatch.setattr(
        project_config.json, "dump",
        lambda payload, handle, **kwargs: (
            calls.append(len(payload["tags"])),
            original_dump(payload, handle, **kwargs),
        )[1],
    )
    assert project_config._write_project(project_app, tmp_path / "large.simproject")
    assert calls == [5000]


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


def test_rockwell_project_requires_only_ip(project_app):
    project_app.brand_menu.value = "Rockwell"
    project_app.tags[0].address = "Start_Button"
    project_app.tags[1].address = "Tank_Level"

    project = project_config.build_project_data(project_app)
    staged = project_config._stage_project_data(project)

    assert staged["plc"] == {
        "brand": "Rockwell",
        "ip": "192.168.1.10",
        "settings": {},
    }
    assert [tag["address"] for tag in staged["tags"]] == [
        "Start_Button",
        "Tank_Level",
    ]


def test_omron_project_preserves_fins_connection_settings(project_app):
    value_type = type(project_app.ip_entry)
    project_app.brand_menu.value = "Omron"
    project_app.port_entry = value_type("9600")
    project_app.destination_node_entry = value_type("10")
    project_app.source_node_entry = value_type("20")
    project_app.tags[0].address = "CIO0.00"
    project_app.tags[1].address = "D300"

    staged = project_config._stage_project_data(
        project_config.build_project_data(project_app)
    )

    assert staged["plc"]["brand"] == "Omron"
    assert staged["plc"]["settings"] == {
        "port": "9600",
        "destination_node": "10",
        "source_node": "20",
    }


def test_simulator_project_has_no_network_or_runtime_values(project_app):
    project_app.brand_menu.value = "Simulator"
    project_app.tags[0].address = "Motor_Run"
    project_app.tags[1].address = "Tank_Level"
    project_app.tag_runtime_values = {"Motor_Run": True, "Tank_Level": 42.5}

    project = project_config.build_project_data(project_app)
    staged = project_config._stage_project_data(project)

    assert staged["plc"] == {
        "brand": "Simulator",
        "ip": "",
        "settings": {},
    }
    assert "runtime_values" not in staged
    assert "tag_runtime_values" not in staged
    assert [tag["address"] for tag in staged["tags"]] == [
        "Motor_Run",
        "Tank_Level",
    ]
