import json
import uuid

import pytest

from core.tag_identity import is_valid_tag_id
from core.tag_model import TagDefinition
from core.tag_runtime import RuntimeTagCache
from ui import project_config, tag_manager


def _legacy_project(*names):
    project = project_config._default_project_data()
    project["schema_version"] = 2
    project["tags"] = [
        {
            "name": name,
            "data_type": "BOOL",
            "direction": "Input",
            "address": f"%DB100.DBX{index}.0",
            "enabled_dashboard": True,
        }
        for index, name in enumerate(names)
    ]
    return project


def _headless_project_open(monkeypatch):
    monkeypatch.setattr(project_config.messagebox, "showerror", lambda *_args: None)
    monkeypatch.setattr(project_config.messagebox, "showwarning", lambda *_args: None)

    def apply_project(app, project, **_kwargs):
        app.tags = [TagDefinition.from_dict(item) for item in project["tags"]]
        return True

    monkeypatch.setattr(project_config, "_apply_project_data", apply_project)


def test_legacy_project_migration_generates_unique_ids_without_mutating_source():
    source = _legacy_project("Start", "Stop")

    migrated = project_config.migrate_project_data(source)

    ids = [item["tag_id"] for item in migrated["tags"]]
    assert source["schema_version"] == 2
    assert all("tag_id" not in item for item in source["tags"])
    assert migrated["schema_version"] == project_config.PROJECT_SCHEMA_VERSION == 4
    assert len(set(ids)) == 2
    assert all(is_valid_tag_id(tag_id) for tag_id in ids)
    assert migrated["_identity_migration_count"] == 2


def test_project_migration_is_idempotent_and_preserves_generated_ids():
    first = project_config.migrate_project_data(_legacy_project("Start", "Stop"))

    second = project_config.migrate_project_data(first)

    assert second == first


def test_independent_unsaved_legacy_opens_generate_different_ids():
    source = _legacy_project("Start")

    first = project_config.migrate_project_data(source)
    second = project_config.migrate_project_data(source)

    assert first["tags"][0]["tag_id"] != second["tags"][0]["tag_id"]


def test_uppercase_identity_is_normalized_during_staging():
    project = _legacy_project("Start")
    expected = uuid.uuid4()
    project["tags"][0]["tag_id"] = str(expected).upper()

    staged = project_config._stage_project_data(project)

    assert staged["tags"][0]["tag_id"] == str(expected)


@pytest.mark.parametrize(
    "tag_id",
    ["not-a-uuid", str(uuid.uuid1())],
    ids=["malformed", "non-v4"],
)
def test_invalid_explicit_identity_is_rejected_before_apply(tag_id):
    project = _legacy_project("Broken")
    project["tags"][0]["tag_id"] = tag_id

    with pytest.raises(project_config.ProjectTagIdentityError, match="invalid tag_id"):
        project_config._stage_project_data(project)


def test_duplicate_identity_is_rejected_before_apply():
    project = _legacy_project("First", "Second")
    duplicate = str(uuid.uuid4())
    for item in project["tags"]:
        item["tag_id"] = duplicate

    with pytest.raises(project_config.ProjectTagIdentityError, match="Duplicate tag_id"):
        project_config._stage_project_data(project)


def test_generated_identity_collision_is_rejected(monkeypatch):
    project = _legacy_project("First", "Second")
    duplicate = str(uuid.uuid4())
    monkeypatch.setattr(project_config, "generate_tag_id", lambda: duplicate)

    with pytest.raises(project_config.ProjectTagIdentityError, match="Duplicate tag_id"):
        project_config._stage_project_data(project)


def test_invalid_project_identity_preserves_active_state(tmp_path, monkeypatch):
    path = tmp_path / "invalid-id.simproject"
    project = _legacy_project("Broken")
    project["tags"][0]["tag_id"] = "invalid"
    path.write_text(json.dumps(project), encoding="utf-8")

    existing = TagDefinition("Existing", "BOOL", "Input", "%DB1.DBX0.0")
    runtime = RuntimeTagCache()
    runtime.update(existing.name, True)
    app = type("App", (), {})()
    app.tags = [existing]
    app.tag_runtime = runtime
    app.project_path = "current.simproject"
    before_runtime = runtime.snapshot()
    errors = []
    monkeypatch.setattr(
        project_config.messagebox,
        "showerror",
        lambda title, message: errors.append((title, message)),
    )
    monkeypatch.setattr(
        project_config,
        "_apply_project_data",
        lambda *_args, **_kwargs: pytest.fail("invalid project must not be applied"),
    )

    assert project_config.open_project_path(app, path) is False
    assert app.tags == [existing]
    assert app.tags[0] is existing
    assert app.tag_runtime.snapshot() == before_runtime
    assert app.project_path == "current.simproject"
    assert "invalid tag_id" in errors[0][1]


def test_legacy_open_save_and_reopen_preserves_ids_and_original_bytes(
    tmp_path, project_app, monkeypatch
):
    legacy_path = tmp_path / "legacy.simproject"
    saved_path = tmp_path / "saved.simproject"
    legacy_path.write_text(json.dumps(_legacy_project("Start", "Stop")), encoding="utf-8")
    original_bytes = legacy_path.read_bytes()
    project_app.tag_runtime = RuntimeTagCache()
    _headless_project_open(monkeypatch)

    assert project_config.open_project_path(project_app, legacy_path) is True
    generated_ids = [tag.tag_id for tag in project_app.tags]
    assert legacy_path.read_bytes() == original_bytes

    assert project_config._write_project(project_app, saved_path) is True
    saved = json.loads(saved_path.read_text(encoding="utf-8"))
    assert [item["tag_id"] for item in saved["tags"]] == generated_ids

    project_app.tags = []
    assert project_config.open_project_path(project_app, saved_path) is True
    assert [tag.tag_id for tag in project_app.tags] == generated_ids


def test_save_as_persists_existing_ids(tmp_path, project_app, monkeypatch):
    path = tmp_path / "copy.simproject"
    expected = [tag.tag_id for tag in project_app.tags]
    monkeypatch.setattr(
        project_config.filedialog,
        "asksaveasfilename",
        lambda **_kwargs: str(path),
    )

    assert project_config.save_project_as(project_app) is True
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert [item["tag_id"] for item in saved["tags"]] == expected


def test_save_rejects_corrupted_in_memory_identity_without_writing(
    tmp_path, project_app, monkeypatch
):
    path = tmp_path / "must-not-exist.simproject"
    project_app.tags[0].tag_id = "corrupted"
    errors = []
    monkeypatch.setattr(
        project_config.messagebox,
        "showerror",
        lambda title, message: errors.append((title, message)),
    )

    assert project_config._write_project(project_app, path) is False
    assert path.exists() is False
    assert "tag identity is invalid" in errors[0][1]


def test_current_project_ids_and_unknown_project_fields_are_preserved():
    project = _legacy_project("Start")
    expected = str(uuid.uuid4())
    project["tags"][0]["tag_id"] = expected
    project["compatible_extension"] = {"vendor": "example", "enabled": True}

    staged = project_config._stage_project_data(project)

    assert staged["tags"][0]["tag_id"] == expected
    assert staged["compatible_extension"] == project["compatible_extension"]


def test_generic_csv_schema_does_not_gain_tag_identity():
    assert "tag_id" not in tag_manager.TAG_CSV_HEADERS
    assert "tag_id" not in tag_manager.TAG_CSV_HEADERS.values()
