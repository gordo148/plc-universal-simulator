import copy
import csv
import json
import math
import time
from types import SimpleNamespace

import pytest

from core.tag_model import TagDefinition
from core.tag_runtime import RuntimeTagCache, RuntimeValueSource
from services.plc_service import PLCService
from ui import alarm_tab, project_config, tag_manager, trend_tab


CSV_HEADER = (
    "name,data_type,direction,address,enabled_sim,enabled_trend,"
    "enabled_alarm,enabled_dashboard\n"
)


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class Recorder:
    def __init__(self):
        self.calls = []

    def configure(self, **kwargs):
        self.calls.append(kwargs)


class Scheduler:
    def __init__(self):
        self.calls = []

    def after(self, delay, callback):
        self.calls.append((delay, callback))


def large_tag_set(count):
    data_types = ("BOOL", "INT", "REAL")
    directions = ("Input", "Feedback", "Output", "Internal")
    return [
        TagDefinition(
            name=f"Tag_{index:04d}",
            data_type=data_types[index % len(data_types)],
            direction=directions[index % len(directions)],
            address=f"memory/{index}",
            enabled_sim=index % 2 == 0,
            enabled_trend=index % 3 == 0,
            enabled_alarm=index % 5 == 0,
            enabled_dashboard=index % 7 == 0,
        )
        for index in range(count)
    ]


def simulator_project(tags):
    project = project_config._default_project_data()
    project["plc"] = {"brand": "Simulator", "ip": "", "settings": {}}
    project["tags"] = [tag.to_dict() for tag in tags]
    return project


@pytest.mark.parametrize("count", [100, 500])
def test_large_mixed_projects_stage_without_data_loss(count):
    tags = large_tag_set(count)

    staged = project_config._stage_project_data(simulator_project(tags))

    assert len(staged["tags"]) == count
    assert {tag["data_type"] for tag in staged["tags"]} == {
        "BOOL",
        "INT",
        "REAL",
    }
    assert staged["tags"][0]["name"] == "Tag_0000"
    assert staged["tags"][-1]["name"] == f"Tag_{count - 1:04d}"


def test_brand_switching_revalidates_existing_tags():
    tags = [
        TagDefinition("SiemensTag", "BOOL", "Input", "%DB100.DBX0.0"),
        TagDefinition("SchneiderTag", "BOOL", "Input", "%M0"),
        TagDefinition("ModbusTag", "INT", "Input", "0"),
        TagDefinition("RockwellTag", "REAL", "Input", "Tank_Level"),
        TagDefinition("OmronTag", "BOOL", "Input", "CIO0.00"),
        TagDefinition("SimulatorTag", "REAL", "Input", "internal/level"),
    ]
    from core.connection_state import ConnectionState
    state = ConnectionState()
    app = SimpleNamespace(tags=tags, connection_state=state)

    expected_valid = {
        "Siemens": {"SiemensTag"},
        "Schneider": {"SchneiderTag"},
        "Modbus TCP": {"SchneiderTag", "ModbusTag"},
        "Rockwell": {"RockwellTag"},
        "Omron": {"OmronTag"},
        "Simulator": {tag.name for tag in tags},
    }
    for selected_brand, expected in expected_valid.items():
        state.set_brand(selected_brand)
        invalid = tag_manager.get_invalid_tags_for_brand(app)
        valid_names = {tag.name for tag in tags if tag not in invalid}
        assert valid_names == expected


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("name,data_type\nTag,BOOL\n", "Missing columns"),
        (CSV_HEADER + "Tag,STRING,Input,A,1,1,0,0\n", "data_type inválido"),
        (CSV_HEADER + "Tag,BOOL,Unknown,A,1,1,0,0\n", "direction inválida"),
        (
            CSV_HEADER + "Tag,BOOL,Input,%DB100.DBX0.0,maybe,1,0,0\n",
            "booleano inválido",
        ),
        (CSV_HEADER + "Tag,REAL,Input,%DB100.DBW20,1,1,0,0\n", "REAL requires"),
    ],
)
def test_invalid_csv_variants_are_rejected(tmp_path, body, message):
    path = tmp_path / "invalid.csv"
    path.write_text(body, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        tag_manager.read_tags_csv(path, "Siemens")


def test_duplicate_csv_tags_are_rejected_before_application(tmp_path):
    path = tmp_path / "duplicates.csv"
    path.write_text(
        CSV_HEADER
        + "Motor,BOOL,Input,%DB100.DBX0.0,1,1,0,0\n"
        + " motor ,BOOL,Input,%DB100.DBX0.1,1,1,0,0\n",
        encoding="utf-8",
    )
    tags = tag_manager.read_tags_csv(path, "Siemens")

    valid, message = tag_manager.normalize_and_validate_tag_names(tags)

    assert valid is False
    assert "duplicado" in message


@pytest.mark.parametrize(
    "mutation",
    [
        lambda project: project.update(format="unknown-format"),
        lambda project: project.update(version=999),
        lambda project: project.pop("plc"),
        lambda project: project.update(tags="not-a-list"),
        lambda project: project.update(runtime_settings=[]),
    ],
)
def test_corrupted_project_structures_are_rejected(mutation):
    project = project_config._default_project_data()
    mutation(project)

    with pytest.raises(ValueError):
        project_config._stage_project_data(project)


def test_duplicate_project_tags_are_rejected_case_insensitively():
    tags = large_tag_set(100)
    duplicate = copy.deepcopy(tags[0])
    duplicate.name = tags[0].name.lower()
    tags.append(duplicate)

    with pytest.raises(ValueError, match="duplicado"):
        project_config._stage_project_data(simulator_project(tags))


def test_offline_simulation_at_500_tag_scale_remains_good():
    tags = large_tag_set(500)
    cache = RuntimeTagCache()
    cache.sync(tags)
    for index, tag in enumerate(tags):
        value = (
            index % 2 == 0
            if tag.data_type == "BOOL"
            else index if tag.data_type == "INT" else index / 10.0
        )
        cache.update(tag.name, value, RuntimeValueSource.SIMULATION)

    service = PLCService(runtime_cache=cache)
    assert service.read(tags) is False

    assert len(cache.snapshot()) == 500
    assert all(cache.get(tag.name).valid for tag in tags)
    assert all(
        cache.get(tag.name).source is RuntimeValueSource.SIMULATION
        for tag in tags
    )


def test_runtime_cache_handles_repeated_500_tag_cycles_quickly():
    tags = large_tag_set(500)
    cache = RuntimeTagCache()
    started = time.perf_counter()

    for cycle in range(100):
        cache.sync(tags)
        for index, tag in enumerate(tags):
            cache.update(tag.name, cycle + index)
        snapshot = cache.snapshot()

    elapsed = time.perf_counter() - started
    assert len(snapshot) == 500
    assert cache.get_value("Tag_0499") == 598
    assert elapsed < 5.0


def test_trend_export_blanks_invalid_and_bad_samples(tmp_path, monkeypatch):
    path = tmp_path / "trend.csv"
    tag = TagDefinition(
        "Pressure",
        "REAL",
        "Feedback",
        "Pressure",
        enabled_trend=True,
    )
    cache = RuntimeTagCache()
    cache.update(tag.name, 12.5)
    good = trend_tab._numeric_value(cache.get_value(tag.name))
    cache.invalidate(tag.name)
    bad = trend_tab._numeric_value(cache.get_value(tag.name))
    invalid = trend_tab._numeric_value("invalid")
    app = SimpleNamespace(
        tags=[tag],
        trend_data={
            "time": [0, 1, 2, 3, 4],
            "tags": {
                tag.name: [good, bad, invalid, math.nan, math.inf],
            },
        },
        status_label=Recorder(),
    )
    monkeypatch.setattr(
        trend_tab.filedialog,
        "asksaveasfilename",
        lambda **_kwargs: str(path),
    )

    trend_tab.export_csv(app)

    with path.open(newline="", encoding="utf-8") as exported:
        rows = list(csv.reader(exported))
    assert rows == [
        ["time_s", "Pressure"],
        ["0", "12.5"],
        ["1", ""],
        ["2", ""],
        ["3", ""],
        ["4", ""],
    ]


def alarm_definition(alarm_type, limit):
    return {
        "source": "Level",
        "type": alarm_type,
        "limit": limit,
        "active": False,
        "ack": False,
        "last_value": 0,
        "timestamp": "-",
    }


def test_alarm_evaluation_covers_hh_h_l_ll_and_bad_quality(monkeypatch):
    tag = TagDefinition(
        "Level",
        "REAL",
        "Feedback",
        "Level",
        enabled_alarm=True,
    )
    cache = RuntimeTagCache()
    alarms = [
        alarm_definition("HIGH HIGH", 90),
        alarm_definition("HIGH", 80),
        alarm_definition("LOW", 20),
        alarm_definition("LOW LOW", 10),
    ]
    from core.connection_state import ConnectionState
    state = ConnectionState(); state.set_brand("Simulator")
    app = SimpleNamespace(
        tags=[tag],
        connection_state=state,
        tag_runtime=cache,
        alarms=alarms,
        alarm_rows=[],
        alarm_status_label=Recorder(),
        app=Scheduler(),
    )
    app.schedule_job = app.app.after
    monkeypatch.setattr(alarm_tab, "record_dashboard_event", lambda *_args: None)

    cache.update("Level", 95.0)
    alarm_tab.scan_alarms(app)
    assert [alarm["active"] for alarm in alarms] == [True, True, False, False]

    cache.update("Level", 5.0)
    alarm_tab.scan_alarms(app)
    assert [alarm["active"] for alarm in alarms] == [False, False, True, True]

    cache.invalidate("Level")
    alarm_tab.scan_alarms(app)
    assert [alarm["active"] for alarm in alarms] == [False, False, False, False]


def test_project_save_and_open_roundtrip_uses_staged_data(
    tmp_path,
    project_app,
    monkeypatch,
):
    path = tmp_path / "qa-roundtrip.simproject"
    project_app.tag_runtime = RuntimeTagCache()
    assert project_config._write_project(project_app, path)
    captured = []
    monkeypatch.setattr(
        project_config.filedialog,
        "askopenfilename",
        lambda **_kwargs: str(path),
    )
    monkeypatch.setattr(
        project_config,
        "_apply_project_data",
        lambda _app, project, **_kwargs: captured.append(project) or True,
    )

    assert project_config.open_project(project_app)

    assert captured[0]["format"] == project_config.PROJECT_FORMAT
    assert [tag["name"] for tag in captured[0]["tags"]] == ["Run", "Speed"]


def test_internal_simulator_stress_reads_and_persists_500_tags():
    tags = large_tag_set(500)
    service = PLCService()
    assert service.connect("Simulator", "")
    assert service.read(tags)

    for index, tag in enumerate(tags):
        if tag.data_type == "BOOL":
            assert service.write_bool(tag, index % 2 == 0) is not None
        else:
            assert service.write_numeric(tag, index + 0.75) is not None

    service.disconnect()
    assert service.connect("Simulator", "")
    assert service.read(tags)

    assert len(service.runtime_cache.snapshot()) == 500
    assert service.runtime_cache.get_value("Tag_0498") is True
    assert service.runtime_cache.get_value("Tag_0499") == 499
