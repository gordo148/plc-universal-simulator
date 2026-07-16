import copy
import csv
import inspect
import json
from types import SimpleNamespace

import pytest

from core.tag_model import TagDefinition
from ui import project_config, tag_manager
from ui import alarm_tab, analog_tab, dashboard_tab, digital_tab, feedback_tab, trend_tab
from ui.table_utils import filter_tags


BASE_HEADERS = [
    "Name", "Data Type", "Direction", "Address", "Sim Enabled",
    "Trend Enabled", "Alarm Enabled", "Dashboard Enabled",
]


def test_model_serializes_comment_and_normalizes_none():
    tag = TagDefinition("Motor", "BOOL", "Input", "%M0.0", comment="Motor em marcha")
    assert tag.to_dict()["comment"] == "Motor em marcha"
    assert TagDefinition.from_dict(tag.to_dict()).comment == "Motor em marcha"
    assert TagDefinition.from_dict({"name": "Old"}).comment == ""
    assert TagDefinition.from_dict({"name": "Null", "comment": None}).comment == ""
    assert copy.deepcopy(tag).comment == "Motor em marcha"


@pytest.mark.parametrize("header", [
    "Comment", "Comments", "Description", "Tag Comment", "Comentario",
    "Comentários", "Descrição", "cOmMeNt",
])
def test_universal_csv_accepts_optional_comment_aliases(tmp_path, header):
    path = tmp_path / "alias.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(BASE_HEADERS + [header])
        writer.writerow(["Motor", "BOOL", "Input", "%M0.0", 1, 0, 0, 1, "Descrição útil"])
    assert tag_manager.read_tags_csv(path, "Siemens")[0].comment == "Descrição útil"


def test_comment_alias_priority_is_deterministic(tmp_path):
    path = tmp_path / "priority.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(BASE_HEADERS + ["Description", "Comments", "Comment"])
        writer.writerow(["Motor", "BOOL", "Input", "%M0.0", 1, 0, 0, 1, "third", "second", "first"])
    assert tag_manager.read_tags_csv(path, "Siemens")[0].comment == "first"


def test_csv_comment_round_trip_preserves_unicode_commas_and_quotes(tmp_path):
    comment = 'Temperatura, depósito "Água" — revisão nº 2'
    source = tmp_path / "source.csv"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(BASE_HEADERS + ["Comment"])
        writer.writerow(["Temperature", "REAL", "Feedback", "%DB30.DBD12", 0, 1, 1, 1, comment])
    imported = tag_manager.read_tags_csv(source, "Siemens")
    exported = tmp_path / "exported.csv"
    tag_manager.write_tags_csv(exported, imported)
    restored = tag_manager.read_tags_csv(exported, "Siemens")
    assert restored[0].comment == comment
    assert "Comment" in exported.read_text(encoding="utf-8").splitlines()[0]


def test_tia_and_schneider_import_existing_comment_column(tmp_path):
    tia = tmp_path / "tia.csv"
    tia.write_text("Name,Data Type,Logical Address,Comment\nRun,Bool,%DB1.DBX0.0,Motor feedback\n", encoding="utf-8")
    schneider = tmp_path / "schneider.csv"
    schneider.write_text("Variable,Type,Address,Comment\nRun,BOOL,%M0,Motor feedback\n", encoding="utf-8")
    assert tag_manager.read_tia_tags_csv(tia)[0].comment == "Motor feedback"
    assert tag_manager.read_schneider_tags_csv(schneider)[0].comment == "Motor feedback"


def test_old_project_and_null_comment_stage_without_schema_change():
    project = project_config._default_project_data()
    schema = project["schema_version"]
    project["tags"] = [TagDefinition("Run", "BOOL", "Input", "%DB1.DBX0.0").to_dict()]
    project["tags"][0].pop("comment")
    staged = project_config._stage_project_data(project)
    assert staged["schema_version"] == schema
    assert staged["tags"][0]["comment"] == ""
    project["tags"][0]["comment"] = None
    assert project_config._stage_project_data(project)["tags"][0]["comment"] == ""


def test_search_matches_comment_name_and_address_case_insensitively():
    tags = [TagDefinition("Pump", "BOOL", "Input", "%M10.0", comment="Bomba de ÁGUA")]
    for query in ("pump", "%m10", "água"):
        assert tag_manager.filter_tag_collection(tags, query) == tags
        assert filter_tags(tags, query) == tags


def test_project_save_and_reopen_preserves_comment(tmp_path, project_app):
    project_app.tags[0].comment = 'Comando "Marcha", principal'
    path = tmp_path / "comments.simproject"
    assert project_config._write_project(project_app, path)
    staged = project_config._stage_project_data(json.loads(path.read_text(encoding="utf-8")))
    assert staged["tags"][0]["comment"] == 'Comando "Marcha", principal'


def test_tag_manager_comment_edit_updates_model(monkeypatch):
    tag = TagDefinition("Run", "BOOL", "Input", "%M0.0", comment="Old")
    table = SimpleNamespace(
        identify_column=lambda _x: "#5", selection=lambda: ("0",),
    )
    app = SimpleNamespace(tag_table=table, tags=[tag])
    monkeypatch.setattr("tkinter.simpledialog.askstring", lambda *_a, **_k: "Edited")
    monkeypatch.setattr(tag_manager, "mark_project_modified", lambda _app: None)
    monkeypatch.setattr(tag_manager, "refresh_tag_table", lambda _app: None)
    tag_manager.edit_tag_comment(app, SimpleNamespace(x=1))
    assert tag.comment == "Edited"


@pytest.mark.parametrize(("module", "needle"), [
    (dashboard_tab, '"comment"'), (trend_tab, '"comment"'),
    (digital_tab, '"comment"'), (analog_tab, '"comment"'),
    (alarm_tab, '"Comment"'), (feedback_tab, '"Comment"'),
])
def test_relevant_interfaces_define_comment_columns(module, needle):
    assert needle in inspect.getsource(module)
