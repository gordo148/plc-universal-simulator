import copy
import json
import uuid

import pytest

from core.tag_model import TagDefinition
from core.tag_runtime import RuntimeTagCache
from core.tag_references import (
    AmbiguousTagReferenceError,
    InvalidTagReferenceError,
    UnresolvedTagReferenceError,
    build_tag_reference_index,
    resolve_tag_reference,
    serialize_tag_reference,
)
from ui import project_config
from ui import alarm_tab
from core.connection_state import ConnectionState


TAG_A_ID = "00000000-0000-4000-8000-000000000011"
TAG_B_ID = "00000000-0000-4000-8000-000000000012"


def _tag(name, tag_id, *, data_type="REAL", direction="Input"):
    return TagDefinition(name, data_type, direction, "%DB1.DBD0", tag_id=tag_id)


def _legacy_feature_project():
    first = _tag("Level", TAG_A_ID)
    second = _tag("Output", TAG_B_ID, direction="Output")
    project = project_config._default_project_data()
    project["schema_version"] = 3
    project["tags"] = [first.to_dict(), second.to_dict()]
    project["dashboard"] = {"enabled_tags": ["Level"]}
    project["trends"] = {
        "enabled_tags": ["Level"],
        "selected_curves": ["Level"],
        "auto_scale": True,
    }
    project["alarms"] = [{"source": "Level", "type": "HIGH", "limit": 10}]
    project["pid"] = {
        "sp_source": "Manual",
        "pv_source": "Level",
        "out_source": "Output",
    }
    project["runtime_settings"] = {
        "digital_inputs": [{"tag": "Level", "mode": "Pulse", "pulse_ms": "250"}],
        "ui_state": {
            "digital": {"selected_row": "Level"},
            "analog": {"selected_row": "Level"},
        },
    }
    project["analog_profiles"] = [{"tag": "Level", "mode": "Ramp"}]
    return project


def test_reference_resolver_prefers_and_normalizes_valid_id():
    tag = _tag("Level", TAG_A_ID)
    index = build_tag_reference_index([tag])

    resolved = resolve_tag_reference(
        {"tag_id": TAG_A_ID.upper(), "tag_name": "obsolete"},
        index,
        context="test",
    )

    assert resolved is tag
    assert serialize_tag_reference(tag) == {"tag_id": TAG_A_ID, "tag_name": "Level"}


def test_reference_resolver_rejects_invalid_and_missing_ids():
    index = build_tag_reference_index([_tag("Level", TAG_A_ID)])

    with pytest.raises(InvalidTagReferenceError, match="invalid tag ID"):
        resolve_tag_reference({"tag_id": "broken"}, index, context="Alarm")
    with pytest.raises(UnresolvedTagReferenceError, match="does not exist"):
        resolve_tag_reference(
            {"tag_id": str(uuid.uuid4())}, index, context="Alarm"
        )


def test_unique_legacy_name_resolves_but_ambiguous_name_does_not():
    first = _tag("Shared", TAG_A_ID)
    index = build_tag_reference_index([first])
    assert resolve_tag_reference("Shared", index, context="legacy") is first

    ambiguous = build_tag_reference_index([first, _tag("Shared", TAG_B_ID)])
    with pytest.raises(AmbiguousTagReferenceError, match="ambiguous"):
        resolve_tag_reference("Shared", ambiguous, context="legacy")


def test_legacy_feature_references_migrate_to_schema_four_ids():
    source = _legacy_feature_project()
    original = copy.deepcopy(source)
    migrated = project_config.migrate_project_data(source)

    assert migrated["schema_version"] == 4
    assert migrated["dashboard"] == {"enabled_tag_ids": [TAG_A_ID]}
    assert migrated["trends"]["enabled_tag_ids"] == [TAG_A_ID]
    assert migrated["trends"]["selected_curve_ids"] == [TAG_A_ID]
    assert migrated["alarms"][0]["source_tag_id"] == TAG_A_ID
    assert migrated["pid"]["pv_source_tag_id"] == TAG_A_ID
    assert migrated["pid"]["out_source_tag_id"] == TAG_B_ID
    assert migrated["runtime_settings"]["digital_inputs"][0]["tag_id"] == TAG_A_ID
    assert migrated["analog_profiles"][0]["tag_id"] == TAG_A_ID
    assert migrated["runtime_settings"]["ui_state"]["digital"]["selected_tag_id"] == TAG_A_ID
    assert source == original


def test_feature_reference_migration_is_idempotent():
    first = project_config.migrate_project_data(_legacy_feature_project())

    assert project_config.migrate_project_data(first) == first


def test_rename_updates_descriptive_names_without_detaching_ids():
    migrated = project_config.migrate_project_data(_legacy_feature_project())
    renamed = copy.deepcopy(migrated)
    renamed["tags"][0]["name"] = "TankLevel"

    staged = project_config._stage_project_data(renamed)

    assert staged["dashboard"]["enabled_tag_ids"] == [TAG_A_ID]
    assert staged["trends"]["selected_curve_ids"] == [TAG_A_ID]
    assert staged["alarms"][0]["source_tag_name"] == "TankLevel"
    assert staged["analog_profiles"][0]["tag_name"] == "TankLevel"


def test_replacement_with_same_name_does_not_inherit_required_reference():
    migrated = project_config.migrate_project_data(_legacy_feature_project())
    replacement = copy.deepcopy(migrated)
    replacement["tags"][0]["tag_id"] = str(uuid.uuid4())

    with pytest.raises(UnresolvedTagReferenceError, match="Alarm 1 source"):
        project_config._stage_project_data(replacement)


def test_optional_stale_reference_is_cleared_with_diagnostic():
    project = _legacy_feature_project()
    project["dashboard"]["enabled_tags"] = ["Deleted"]

    migrated = project_config.migrate_project_data(project)

    assert migrated["dashboard"]["enabled_tag_ids"] == []
    assert "Optional reference was cleared" in "\n".join(migrated["_migration_warnings"])


def test_build_project_data_uses_only_id_based_feature_fields(project_app):
    project_app.tags[0].enabled_dashboard = True
    project_app.tags[0].enabled_trend = True
    project_app.trend_visible_tags = {project_app.tags[0].tag_id}
    project_app.alarms = [
        {"source_tag_id": project_app.tags[1].tag_id, "source": "Speed", "type": "HIGH", "limit": 10}
    ]

    project = project_config.build_project_data(project_app)

    assert "enabled_tags" not in project["dashboard"]
    assert project["dashboard"]["enabled_tag_ids"] == [project_app.tags[0].tag_id]
    assert "selected_curves" not in project["trends"]
    assert project["alarms"][0]["source_tag_id"] == project_app.tags[1].tag_id
    assert "source" not in project["alarms"][0]


def test_alarm_runtime_association_survives_rename_by_id():
    tag = _tag("Level", TAG_A_ID)
    tag.enabled_alarm = True
    state = ConnectionState()
    state.set_brand("Simulator")
    runtime = RuntimeTagCache()
    runtime.sync([tag])
    runtime.update(tag, 25)
    alarm = {"source_tag_id": tag.tag_id, "source": "Level"}
    app = type("App", (), {})()
    app.tags = [tag]
    app.connection_state = state
    app.tag_runtime = runtime

    tag.name = "TankLevel"

    assert alarm_tab.get_alarm_value(app, alarm) == 25
    assert alarm["source"] == "TankLevel"


def test_legacy_reference_project_open_does_not_rewrite_source(
    tmp_path, project_app, monkeypatch
):
    path = tmp_path / "legacy-features.simproject"
    path.write_text(json.dumps(_legacy_feature_project()), encoding="utf-8")
    original = path.read_bytes()
    project_app.tag_runtime = RuntimeTagCache()
    applied = []
    monkeypatch.setattr(
        project_config,
        "_apply_project_data",
        lambda _app, project, **_kwargs: applied.append(project) or True,
    )
    monkeypatch.setattr(project_config.messagebox, "showwarning", lambda *_args: None)

    assert project_config.open_project_path(project_app, path) is True
    assert path.read_bytes() == original
    assert applied[0]["alarms"][0]["source_tag_id"] == TAG_A_ID
