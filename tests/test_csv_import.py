from types import SimpleNamespace

import pytest

from core.tag_model import TagDefinition
from core.tag_runtime import RuntimeTagCache
from ui import tag_manager


CSV_HEADER = (
    "name,data_type,direction,address,enabled_sim,enabled_trend,"
    "enabled_alarm,enabled_dashboard\n"
)

ACCENTED_NAME = "Válvula_áéíóú_ãõ_ç_ºª"


@pytest.mark.parametrize(
    ("encoding", "bom"),
    [
        ("utf-8", False),
        ("utf-8-sig", True),
        ("cp1252", False),
        ("latin-1", False),
    ],
    ids=["utf-8", "utf-8-bom", "windows-1252", "latin-1"],
)
def test_universal_csv_encoding_and_accents(tmp_path, encoding, bom):
    path = tmp_path / f"tags-{encoding}.csv"
    body = CSV_HEADER + f"{ACCENTED_NAME},BOOL,Input,DBX0.0,1,0,0,1\n"
    data = body.encode(encoding)
    if bom:
        assert data.startswith(b"\xef\xbb\xbf")
    path.write_bytes(data)

    tags = tag_manager.read_tags_csv(path, "Siemens")

    assert tags[0].name == ACCENTED_NAME


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp1252", "latin-1"])
def test_tia_csv_encoding_and_accents(tmp_path, encoding):
    path = tmp_path / f"tia-{encoding}.csv"
    body = f"Name,Data Type,Logical Address,Comment\n{ACCENTED_NAME},Bool,%DBX0.0,Descrição ç ºª\n"
    path.write_bytes(body.encode(encoding))

    tags = tag_manager.read_tia_tags_csv(path)

    assert tags[0].name == ACCENTED_NAME


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp1252", "latin-1"])
def test_schneider_csv_encoding_and_accents(tmp_path, encoding):
    path = tmp_path / f"schneider-{encoding}.csv"
    body = f"Variable,Type,Address,Comment\n{ACCENTED_NAME},BOOL,%M0,Descrição ç ºª\n"
    path.write_bytes(body.encode(encoding))

    tags = tag_manager.read_schneider_tags_csv(path)

    assert tags[0].name == ACCENTED_NAME


def test_valid_universal_csv(tmp_path):
    path = tmp_path / "tags.csv"
    path.write_text(
        CSV_HEADER
        + "Start,BOOL,Input,DBX0.0,1,true,0,yes\n"
        + "Setpoint,REAL,Output,DBD20,0,1,false,true\n",
        encoding="utf-8",
    )

    tags = tag_manager.read_tags_csv(path, "Siemens")

    assert [(tag.name, tag.data_type) for tag in tags] == [
        ("Start", "BOOL"),
        ("Setpoint", "REAL"),
    ]
    assert tags[0].enabled_sim is True
    assert tags[1].enabled_alarm is False


def test_csv_with_trailing_empty_column_is_accepted(tmp_path):
    path = tmp_path / "tags_trailing_column.csv"
    path.write_text(
        CSV_HEADER.rstrip("\n")
        + ",\n"
        + "Tag1,REAL,Input,DBD0,1,1,0,1,0\n",
        encoding="utf-8",
    )

    tags = tag_manager.read_tags_csv(path, "Siemens")

    assert len(tags) == 1
    assert tags[0].name == "Tag1"
    assert tags[0].enabled_dashboard is True


def test_csv_with_extra_trailing_row_value_is_accepted(tmp_path):
    path = tmp_path / "tags_extra_value.csv"
    path.write_text(
        CSV_HEADER + "Tag1,BOOL,Input,DBX0.0,1,0,0,1,spreadsheet\n",
        encoding="utf-8",
    )

    tags = tag_manager.read_tags_csv(path, "Siemens")

    assert [tag.name for tag in tags] == ["Tag1"]


def test_csv_imports_more_than_seventy_siemens_tags(tmp_path):
    path = tmp_path / "many_siemens_tags.csv"
    rows = [
        f"Tag_{index:02d},BOOL,Input,DBX{index // 8}.{index % 8},1,0,0,0\n"
        for index in range(75)
    ]
    path.write_text(CSV_HEADER + "".join(rows), encoding="cp1252")

    tags = tag_manager.read_tags_csv(path, "Siemens")

    assert len(tags) == 75
    assert tags[-1].name == "Tag_74"


def test_excel_exported_csv_with_spreadsheet_columns_is_accepted(tmp_path):
    path = tmp_path / "excel_tags.csv"
    path.write_text(
        "\ufeff name ; data_type ; direction ; address ; enabled_sim ; "
        "enabled_trend ; enabled_alarm ; enabled_dashboard ; Unnamed: 8\r\n"
        "Tag1;REAL;Input;DBD0;1;1;0;1;\r\n",
        encoding="utf-8",
    )

    tags = tag_manager.read_tags_csv(path, "Siemens")

    assert len(tags) == 1
    assert tags[0].name == "Tag1"
    assert tags[0].address == "DBD0"


def test_missing_csv_columns_error_lists_missing_and_detected_columns(tmp_path):
    path = tmp_path / "missing_columns.csv"
    path.write_text(" name , data_type , Unnamed: 2\nTag,BOOL,\n", encoding="utf-8")

    with pytest.raises(ValueError) as error:
        tag_manager.read_tags_csv(path, "Siemens")

    message = str(error.value)
    assert "Missing columns: direction, address" in message
    assert "enabled_dashboard" in message
    assert "Detected columns: name, data_type" in message


def test_invalid_csv_address_is_rejected(tmp_path):
    path = tmp_path / "invalid.csv"
    path.write_text(
        CSV_HEADER + "Broken,REAL,Input,DBW20,1,1,0,0\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="linha 2"):
        tag_manager.read_tags_csv(path, "Siemens")


def test_invalid_csv_does_not_partially_replace_tags(tmp_path, monkeypatch):
    path = tmp_path / "partial.csv"
    path.write_text(
        CSV_HEADER
        + "Valid,BOOL,Input,DBX0.0,1,1,0,0\n"
        + "Invalid,REAL,Input,DBW20,1,1,0,0\n",
        encoding="utf-8",
    )
    original = [TagDefinition("Existing", "BOOL", "Input", "DBX1.0")]
    app = SimpleNamespace(
        tags=original,
        brand_menu=SimpleNamespace(get=lambda: "Siemens"),
    )
    errors = []
    monkeypatch.setattr(
        tag_manager.filedialog,
        "askopenfilename",
        lambda **_kwargs: str(path),
    )
    monkeypatch.setattr(
        tag_manager.messagebox,
        "showerror",
        lambda title, message: errors.append((title, message)),
    )

    tag_manager.import_tags_csv(app)

    assert app.tags is original
    assert [tag.name for tag in app.tags] == ["Existing"]
    assert errors


def test_failed_ui_refresh_restores_tags_and_runtime_without_raising(monkeypatch):
    original = [TagDefinition("Existing", "BOOL", "Input", "DBX1.0")]
    imported = [TagDefinition("Imported", "BOOL", "Input", "DBX2.0")]
    cache = RuntimeTagCache()
    cache.sync(original)
    cache.update("Existing", True)
    original_snapshot = cache.snapshot()
    refresh_calls = 0
    generate_calls = 0

    def refresh(_app):
        nonlocal refresh_calls
        refresh_calls += 1

    def fail_after_runtime_mutation():
        nonlocal generate_calls
        generate_calls += 1
        cache.sync(app.tags)
        if generate_calls == 1:
            raise RuntimeError("tab rebuild failed")

    errors = []
    app = SimpleNamespace(
        tags=original,
        tag_runtime=cache,
        generate_signals=fail_after_runtime_mutation,
        status_label=SimpleNamespace(configure=lambda **_kwargs: None),
    )
    monkeypatch.setattr(tag_manager, "refresh_tag_table", refresh)
    monkeypatch.setattr(
        tag_manager.messagebox,
        "showerror",
        lambda title, message: errors.append((title, message)),
    )

    result = tag_manager.apply_imported_tags(
        app, imported, "Import error", "Imported"
    )

    assert result is False
    assert app.tags is original
    assert cache.snapshot() == original_snapshot
    assert refresh_calls == 2
    assert errors == [(
        "Import error",
        "Import could not be completed. Your previous tags were restored.",
    )]


def test_import_does_not_crash_when_refresh_and_rollback_refresh_fail(monkeypatch):
    original = [TagDefinition("Existing", "BOOL", "Input", "DBX1.0")]
    imported = [TagDefinition("Imported", "BOOL", "Input", "DBX2.0")]
    errors = []
    app = SimpleNamespace(
        tags=original,
        generate_signals=lambda: None,
        status_label=SimpleNamespace(configure=lambda **_kwargs: None),
    )
    monkeypatch.setattr(
        tag_manager,
        "refresh_tag_table",
        lambda _app: (_ for _ in ()).throw(RuntimeError("render failed")),
    )
    monkeypatch.setattr(
        tag_manager.messagebox,
        "showerror",
        lambda title, message: errors.append((title, message)),
    )

    result = tag_manager.apply_imported_tags(
        app, imported, "Import error", "Imported"
    )

    assert result is False
    assert app.tags is original
    assert errors


def test_rockwell_csv_preserves_symbolic_tag_case(tmp_path):
    path = tmp_path / "rockwell.csv"
    path.write_text(
        CSV_HEADER + "Tank,REAL,Input,Tank_Level,1,1,0,0\n",
        encoding="utf-8",
    )

    tags = tag_manager.read_tags_csv(path, "Rockwell")

    assert tags[0].address == "Tank_Level"
