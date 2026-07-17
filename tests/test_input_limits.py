import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.input_limits import (
    InputFileTooLargeError,
    MAX_CSV_FILE_SIZE_BYTES,
    MAX_PROJECT_FILE_SIZE_BYTES,
    validate_input_file_size,
)
from core.tag_model import TagDefinition
from core.tag_runtime import RuntimeTagCache
from ui import project_config, tag_manager


GENERIC_CSV = (
    "name,data_type,direction,address,enabled_sim,enabled_trend,"
    "enabled_alarm,enabled_dashboard\n"
    "Start,BOOL,Input,%DB100.DBX0.0,1,0,0,1\n"
)
TIA_CSV = "Name,Data Type,Logical Address\nStart,Bool,%DB100.DBX0.0\n"
SCHNEIDER_CSV = "Variable,Type,Address\nStart,BOOL,%M0\n"


def test_default_input_limits_are_generous_and_explicit():
    assert MAX_PROJECT_FILE_SIZE_BYTES == 50 * 1024 * 1024
    assert MAX_CSV_FILE_SIZE_BYTES == 25 * 1024 * 1024


@pytest.mark.parametrize("as_string", [False, True], ids=["path", "string"])
def test_size_validator_accepts_file_exactly_at_limit(tmp_path, as_string):
    path = tmp_path / "exact.input"
    path.write_bytes(b"12345678")
    supplied_path = str(path) if as_string else path

    assert validate_input_file_size(supplied_path, 8, "Test") == path


def test_size_validator_rejects_above_limit_and_logs_metadata_only(
    tmp_path, caplog
):
    path = tmp_path / "oversized.input"
    secret_content = "SECRET-CONTENT-MUST-NOT-BE-LOGGED"
    path.write_text(secret_content, encoding="utf-8")

    with pytest.raises(InputFileTooLargeError) as raised:
        validate_input_file_size(path, 10, "Project")

    error = raised.value
    assert error.path == path
    assert error.actual_size == path.stat().st_size
    assert error.maximum_size == 10
    assert error.file_category == "Project"
    assert str(path) in caplog.text
    assert f"size_bytes={path.stat().st_size}" in caplog.text
    assert "limit_bytes=10" in caplog.text
    assert secret_content not in caplog.text


def test_size_validator_preserves_stat_errors(tmp_path):
    missing = tmp_path / "missing.csv"

    with pytest.raises(FileNotFoundError):
        validate_input_file_size(str(missing), 10, "CSV")


@pytest.mark.parametrize("remaining_bytes", [0, 1], ids=["exact", "below"])
def test_project_at_or_below_limit_opens_normally(
    tmp_path, project_app, monkeypatch, remaining_bytes
):
    path = tmp_path / "valid.simproject"
    project_app.tag_runtime = RuntimeTagCache()
    assert project_config._write_project(project_app, path)
    monkeypatch.setattr(
        project_config,
        "MAX_PROJECT_FILE_SIZE_BYTES",
        path.stat().st_size + remaining_bytes,
    )
    applied = []
    monkeypatch.setattr(
        project_config,
        "_apply_project_data",
        lambda _app, project, **_kwargs: applied.append(project) or True,
    )

    assert project_config.open_project_path(project_app, str(path)) is True
    assert applied[0]["format"] == project_config.PROJECT_FORMAT


def test_oversized_project_is_rejected_before_parse_or_migration(
    tmp_path, monkeypatch, caplog
):
    path = tmp_path / "oversized.simproject"
    path.write_text('{"private": "do not log this content"}', encoding="utf-8")
    monkeypatch.setattr(project_config, "MAX_PROJECT_FILE_SIZE_BYTES", 1)
    monkeypatch.setattr(
        project_config.json,
        "load",
        lambda *_args, **_kwargs: pytest.fail("JSON parsing must not run"),
    )
    monkeypatch.setattr(
        project_config,
        "migrate_project_data",
        lambda *_args: pytest.fail("migration must not run"),
    )
    monkeypatch.setattr(
        project_config,
        "_apply_project_data",
        lambda *_args, **_kwargs: pytest.fail("application must not run"),
    )
    errors = []
    monkeypatch.setattr(
        project_config.messagebox,
        "showerror",
        lambda title, message: errors.append((title, message)),
    )
    original_tags = [TagDefinition("Existing", "BOOL", "Input", "%M0.0")]
    app = SimpleNamespace(tags=original_tags, project_path="current.simproject")

    assert project_config.open_project_path(app, path) is False
    assert app.tags is original_tags
    assert app.project_path == "current.simproject"
    assert "exceeds the maximum supported size" in errors[0][1]
    assert str(path) in caplog.text
    assert "size_bytes=" in caplog.text
    assert "limit_bytes=1" in caplog.text
    assert "do not log this content" not in caplog.text


@pytest.mark.parametrize("remaining_bytes", [0, 1], ids=["exact", "below"])
def test_generic_csv_at_or_below_limit_imports_normally(
    tmp_path, monkeypatch, remaining_bytes
):
    path = tmp_path / "generic.csv"
    path.write_text(GENERIC_CSV, encoding="utf-8")
    monkeypatch.setattr(
        tag_manager,
        "MAX_CSV_FILE_SIZE_BYTES",
        path.stat().st_size + remaining_bytes,
    )

    tags = tag_manager.read_tags_csv(str(path), "Siemens")

    assert [tag.name for tag in tags] == ["Start"]


@pytest.mark.parametrize(
    ("reader", "body"),
    [
        (tag_manager.read_tags_csv, GENERIC_CSV),
        (tag_manager.read_tia_tags_csv, TIA_CSV),
        (tag_manager.read_schneider_tags_csv, SCHNEIDER_CSV),
    ],
    ids=["generic", "tia", "schneider"],
)
def test_all_csv_readers_reject_before_full_byte_read(
    tmp_path, monkeypatch, reader, body
):
    path = tmp_path / "oversized.csv"
    path.write_text(body, encoding="utf-8")
    monkeypatch.setattr(tag_manager, "MAX_CSV_FILE_SIZE_BYTES", 1)
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda *_args: pytest.fail("full byte read must not run"),
    )
    monkeypatch.setattr(
        tag_manager.csv.Sniffer,
        "sniff",
        lambda *_args, **_kwargs: pytest.fail("format detection must not run"),
    )

    with pytest.raises(InputFileTooLargeError):
        reader(path)


@pytest.mark.parametrize(
    ("reader", "body", "expected_name"),
    [
        (tag_manager.read_tags_csv, GENERIC_CSV, "Start"),
        (tag_manager.read_tia_tags_csv, TIA_CSV, "Start"),
        (tag_manager.read_schneider_tags_csv, SCHNEIDER_CSV, "Start"),
    ],
    ids=["generic", "tia", "schneider"],
)
def test_valid_csv_dialects_remain_compatible(
    tmp_path, reader, body, expected_name
):
    path = tmp_path / "valid.csv"
    path.write_text(body, encoding="utf-8")

    tags = reader(path)

    assert [tag.name for tag in tags] == [expected_name]


@pytest.mark.parametrize(
    ("importer", "body"),
    [
        (tag_manager.import_tags_csv, GENERIC_CSV),
        (tag_manager.import_tia_csv, TIA_CSV),
        (tag_manager.import_schneider_csv, SCHNEIDER_CSV),
    ],
    ids=["generic", "tia", "schneider"],
)
def test_oversized_csv_ui_import_preserves_tags_and_shows_clear_error(
    tmp_path, monkeypatch, importer, body
):
    path = tmp_path / "oversized.csv"
    path.write_text(body, encoding="utf-8")
    monkeypatch.setattr(tag_manager, "MAX_CSV_FILE_SIZE_BYTES", 1)
    monkeypatch.setattr(
        tag_manager.filedialog,
        "askopenfilename",
        lambda **_kwargs: str(path),
    )
    monkeypatch.setattr(tag_manager, "connection_brand", lambda _app: "Siemens")
    errors = []
    monkeypatch.setattr(
        tag_manager.messagebox,
        "showerror",
        lambda title, message: errors.append((title, message)),
    )
    original_tags = [TagDefinition("Existing", "BOOL", "Input", "%M0.0")]
    app = SimpleNamespace(tags=original_tags)

    importer(app)

    assert app.tags is original_tags
    assert [tag.name for tag in app.tags] == ["Existing"]
    assert "exceeds the maximum supported size" in errors[0][1]


def test_existing_project_fixture_is_below_limit_and_valid():
    path = Path(__file__).resolve().parents[1] / "configs" / "EDPGER02.simproject"

    validate_input_file_size(path, MAX_PROJECT_FILE_SIZE_BYTES, "Project")
    with path.open(encoding="utf-8") as project_file:
        staged = project_config._stage_project_data(json.load(project_file))

    assert staged["format"] == project_config.PROJECT_FORMAT
