import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.tag_model import TagDefinition
from ui import project_config, tag_manager
from ui.analog_profiles import DEFAULT_ANALOG_PROFILE, normalize_analog_profile


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
    project_app.connection_state.set_brand("Modbus TCP")
    project_app.connection_state.port = "1502"
    project_app.connection_state.slave_id = "7"

    project = project_config.build_project_data(project_app)
    staged = project_config._stage_project_data(project)

    assert staged["plc"] == {
        "brand": "Modbus TCP",
        "ip": "192.168.1.10",
        "settings": {"port": "1502", "slave_id": "7"},
    }


def test_rockwell_project_requires_only_ip(project_app):
    project_app.connection_state.set_brand("Rockwell")
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
    project_app.connection_state.set_brand("Omron")
    project_app.connection_state.omron_port = "9600"
    project_app.connection_state.destination_node = "10"
    project_app.connection_state.source_node = "20"
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
    project_app.connection_state.set_brand("Simulator")
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


def test_analog_profile_configuration_keeps_project_v1_format(project_app):
    project_app.tags[1].direction = "Input"
    project_app._analog_profile_cache = {
        "Speed": {
            "tag": "Speed", "mode": "Ramp", "min": "10", "max": "90",
            "step": "5", "interval_ms": "250",
        }
    }
    project = project_config.build_project_data(project_app)
    staged = project_config._stage_project_data(project)

    assert staged["version"] == project_config.PROJECT_VERSION == 1
    assert staged["analog_profiles"][0]["mode"] == "Ramp"
    assert staged["analog_profiles"][0]["enabled_sim"] is False
    assert "analog_simulations" not in staged


def test_bulk_analog_modes_survive_project_save_and_load(project_app, monkeypatch):
    project_app.tags[1].direction = "Input"
    project_app.tags[1].enabled_sim = False
    project_app.tags.append(
        TagDefinition("Level", "REAL", "Input", "DBD24", enabled_sim=False)
    )
    project_app._analog_profile_cache = {
        "Speed": {
            "tag": "Speed", "mode": "Manual", "min": "1", "max": "10",
            "step": "2", "interval_ms": "250",
        },
        "Level": {
            "tag": "Level", "mode": "Random", "min": "4", "max": "40",
            "step": "3", "interval_ms": "500",
        },
    }
    project_app.mark_project_modified = lambda: None
    monkeypatch.setattr(tag_manager, "refresh_tag_table", lambda _app: None)
    tag_manager.set_all_tag_option(project_app, "enabled_sim", True)

    staged = project_config._stage_project_data(
        project_config.build_project_data(project_app)
    )
    restored = SimpleNamespace(
        tags=project_app.tags, analog_controls=[], analog_tags=[],
        _analog_profile_cache={}
    )
    project_config._restore_analog_profiles(restored, staged["analog_profiles"])

    assert restored._analog_profile_cache["Speed"]["mode"] == "Ramp"
    assert restored._analog_profile_cache["Speed"]["step"] == "2"
    assert restored._analog_profile_cache["Level"]["mode"] == "Random"


def _profile_restore_app(tags, *, structure_initialized=False, table_tags=None):
    return SimpleNamespace(
        tags=tags,
        analog_controls=[],
        analog_tags=[],
        _analog_profile_cache={},
        _analog_structure_initialized=structure_initialized,
        _analog_table_tags=list(table_tags or []),
    )


def test_legacy_v1_project_without_analog_profiles_loads_with_defaults():
    project = project_config._default_project_data()
    project.pop("analog_profiles")
    project["tags"] = [
        TagDefinition("LegacyLevel", "REAL", "Input", "DBD0", True).to_dict()
    ]

    staged = project_config._stage_project_data(project)
    tags = [TagDefinition.from_dict(item) for item in staged["tags"]]
    app = _profile_restore_app(tags)
    project_config._restore_analog_profiles(app, staged["analog_profiles"])

    profile = app._analog_profile_cache["LegacyLevel"]
    assert profile == {
        "tag": "LegacyLevel",
        **DEFAULT_ANALOG_PROFILE,
        "enabled_sim": True,
    }


def test_partial_and_older_key_profile_data_is_normalized_per_field():
    tag = TagDefinition("Level", "REAL", "Input", "DBD0", True)

    profile = normalize_analog_profile(
        {
            "profile_mode": "ramp",
            "minimum": "10",
            "maximum": "90.5",
            "step_value": "bad",
            "interval": "25",
        },
        tag,
    )

    assert profile["mode"] == "Ramp"
    assert profile["min"] == "10"
    assert profile["max"] == "90.5"
    assert profile["step"] == DEFAULT_ANALOG_PROFILE["step"]
    assert profile["interval_ms"] == "100"
    assert profile["enabled_sim"] is True


def test_invalid_profile_fields_do_not_discard_valid_mode_or_other_values():
    tag = TagDefinition("Level", "REAL", "Input", "DBD0")
    profile = normalize_analog_profile(
        {
            "mode": "Random",
            "min": "not-a-number",
            "max": "100",
            "step": None,
            "interval_ms": "250.0",
        },
        tag,
    )

    assert profile["mode"] == "Random"
    assert profile["min"] == DEFAULT_ANALOG_PROFILE["min"]
    assert profile["max"] == "100"
    assert profile["step"] == DEFAULT_ANALOG_PROFILE["step"]
    assert profile["interval_ms"] == "250"


def test_one_malformed_analog_profile_does_not_abort_other_tags(caplog):
    tags = [
        TagDefinition("Broken", "REAL", "Input", "DBD0"),
        TagDefinition("Valid", "REAL", "Input", "DBD4"),
    ]
    app = _profile_restore_app(tags)

    project_config._restore_analog_profiles(app, [
        "invalid-profile",
        {
            "tag": "Valid", "mode": "Step", "min": "1", "max": "9",
            "step": "2", "interval_ms": "200",
        },
    ])

    assert app._analog_profile_cache["Broken"]["mode"] == "Manual"
    assert app._analog_profile_cache["Valid"]["mode"] == "Step"
    assert "tag=Broken" in caplog.text


def test_canonical_profiles_exist_before_tree_rows_are_refreshed(monkeypatch):
    tags = [TagDefinition("Level", "REAL", "Input", "DBD0")]
    app = _profile_restore_app(
        tags,
        structure_initialized=True,
        table_tags=tags,
    )
    from ui import analog_tab
    refreshed = []
    monkeypatch.setattr(analog_tab, "sync_selected_editor_from_canonical", lambda _app: None)

    def assert_canonical_exists(target, tag_name):
        assert target._analog_profile_cache[tag_name]["mode"] == "Ramp"
        refreshed.append(tag_name)

    monkeypatch.setattr(analog_tab, "refresh_analog_tree_row", assert_canonical_exists)
    project_config._restore_analog_profiles(app, [{"tag": "Level", "mode": "Ramp"}])

    assert refreshed == ["Level"]


def test_edpger02_project_restores_without_editor_controls_or_rollback():
    path = Path(__file__).resolve().parents[1] / "configs" / "EDPGER02.simproject"
    with path.open(encoding="utf-8") as project_file:
        staged = project_config._stage_project_data(json.load(project_file))
    tags = [TagDefinition.from_dict(item) for item in staged["tags"]]
    analog_tags = [
        tag for tag in tags
        if tag.direction == "Input" and tag.data_type in ("INT", "REAL")
    ]
    app = _profile_restore_app(tags, structure_initialized=True)

    project_config._restore_analog_profiles(app, staged["analog_profiles"])

    assert len(analog_tags) == 41
    assert set(app._analog_profile_cache) == {tag.name for tag in analog_tags}
    assert all(
        app._analog_profile_cache[tag.name]["mode"] == "Manual"
        for tag in analog_tags
    )
    assert all(
        app._analog_profile_cache[tag.name]["enabled_sim"] is True
        for tag in analog_tags
    )


def test_keyed_and_null_legacy_profile_sections_are_accepted():
    project = project_config._default_project_data()
    project["tags"] = [
        TagDefinition("Level", "REAL", "Input", "DBD0").to_dict()
    ]
    project["analog_profiles"] = {
        "Level": {"mode": "Ramp", "min": "2", "max": "8"}
    }
    staged = project_config._stage_project_data(project)
    assert staged["analog_profiles"][0]["tag"] == "Level"
    assert staged["analog_profiles"][0]["mode"] == "Ramp"

    project["analog_profiles"] = None
    assert project_config._stage_project_data(project)["analog_profiles"] == []


def test_genuinely_invalid_project_structure_is_still_rejected():
    project = project_config._default_project_data()
    project["tags"] = {"Level": {"data_type": "REAL"}}
    with pytest.raises(ValueError, match="Lista de tags inválida"):
        project_config._stage_project_data(project)
