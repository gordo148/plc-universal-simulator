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


def test_empty_boolean_cells_are_false_for_all_boolean_columns(tmp_path):
    path = tmp_path / "empty_boolean_cells.csv"
    path.write_text(
        CSV_HEADER + "Start,BOOL,Input,DBX0.0,,,,\n",
        encoding="utf-8",
    )

    tags = tag_manager.read_tags_csv(path, "Siemens")

    assert tags[0].enabled_sim is False
    assert tags[0].enabled_trend is False
    assert tags[0].enabled_alarm is False
    assert tags[0].enabled_dashboard is False


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", True),
        ("true", True),
        ("yes", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("no", False),
        ("off", False),
        ("", False),
    ],
)
def test_csv_boolean_values(value, expected):
    assert tag_manager.parse_csv_bool(value) is expected


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


def test_csv_imports_five_hundred_mixed_siemens_tags(tmp_path):
    path = tmp_path / "five_hundred_tags.csv"
    rows = []
    for index in range(500):
        if index % 3 == 0:
            rows.append(f"Bool{index},BOOL,Input,DBX{index // 8}.{index % 8},1,0,0,1\n")
        elif index % 3 == 1:
            rows.append(f"Int{index},INT,Input,DBW{index * 2},1,0,0,1\n")
        else:
            rows.append(f"Real{index},REAL,Input,DBD{index * 4},1,1,0,0\n")
    path.write_text(CSV_HEADER + "".join(rows), encoding="utf-8")

    tags = tag_manager.read_tags_csv(path, "Siemens")

    assert len(tags) == 500
    assert {tag.data_type for tag in tags} == {"BOOL", "INT", "REAL"}


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


def test_import_does_not_rebuild_signals_or_runtime(monkeypatch):
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

    assert result is True
    assert app.tags is imported
    assert cache.snapshot() == original_snapshot
    assert refresh_calls == 1
    assert generate_calls == 0
    assert errors == []


class _ImportButton:
    def __init__(self):
        self.states = []

    def configure(self, **kwargs):
        if "state" in kwargs:
            self.states.append(kwargs["state"])


def _async_import_app(original, refresh):
    button = _ImportButton()
    return SimpleNamespace(
        tags=original,
        is_rebuilding=False,
        refresh_after_import=refresh,
        generate_signals=lambda: (_ for _ in ()).throw(
            AssertionError("generate_signals must not run during staged import")
        ),
        status_label=SimpleNamespace(configure=lambda **_kwargs: None),
        tag_import_csv_button=button,
    ), button


def test_staged_import_refreshes_once_without_recursive_generate(monkeypatch):
    original = [TagDefinition("Old", "BOOL", "Input", "DBX0.0")]
    imported = [
        TagDefinition(f"Tag{i}", "BOOL", "Input", f"DBX{i // 8}.{i % 8}")
        for i in range(73)
    ]
    refresh_calls = 0

    def refresh(done, _failed):
        nonlocal refresh_calls
        refresh_calls += 1
        done()

    app, button = _async_import_app(original, refresh)
    monkeypatch.setattr(tag_manager.messagebox, "showerror", lambda *_args: None)

    assert tag_manager.apply_imported_tags(app, imported, "Error", "Done") is True
    assert refresh_calls == 1
    assert app.tags is imported
    assert app.is_rebuilding is False
    assert button.states == ["disabled", "normal"]


def test_staged_import_rolls_back_and_always_resets_state(monkeypatch):
    original = [TagDefinition("Old", "BOOL", "Input", "DBX0.0")]
    imported = [TagDefinition("New", "BOOL", "Input", "DBX1.0")]
    refresh_calls = 0

    def refresh(done, failed):
        nonlocal refresh_calls
        refresh_calls += 1
        if refresh_calls == 1:
            failed(RuntimeError("refresh failed"))
        else:
            done()

    errors = []
    app, button = _async_import_app(original, refresh)
    monkeypatch.setattr(
        tag_manager.messagebox,
        "showerror",
        lambda *args: errors.append(args),
    )

    assert tag_manager.apply_imported_tags(app, imported, "Error", "Done") is True
    assert app.tags is original
    assert app.is_rebuilding is False
    assert button.states[-1] == "normal"
    assert errors


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


def test_bulk_tag_option_refreshes_once_without_generating_signals(monkeypatch):
    tags = [
        TagDefinition(f"Tag{i}", "BOOL", "Input", f"DBX0.{i}")
        for i in range(4)
    ]
    refreshed = []
    modified = []
    app = SimpleNamespace(
        tags=tags,
        generate_signals=lambda: (_ for _ in ()).throw(
            AssertionError("bulk selection must not generate signals")
        ),
        mark_project_modified=lambda: modified.append(True),
    )
    monkeypatch.setattr(
        tag_manager, "refresh_tag_table", lambda target: refreshed.append(target)
    )

    tag_manager.set_all_tag_option(app, "enabled_alarm", True)

    assert all(tag.enabled_alarm for tag in tags)
    assert refreshed == [app]
    assert modified == [True]


class _MasterCheckbox:
    def __init__(self):
        self.states = set()

    def state(self, changes):
        for change in changes:
            if change.startswith("!"):
                self.states.discard(change[1:])
            else:
                self.states.add(change)


def test_master_tag_option_has_all_three_states():
    checkbox = _MasterCheckbox()
    tags = [
        TagDefinition("A", "BOOL", "Input", "DBX0.0", enabled_alarm=True),
        TagDefinition("B", "BOOL", "Input", "DBX0.1", enabled_alarm=False),
    ]
    app = SimpleNamespace(
        tags=tags,
        tag_master_checkboxes={"enabled_alarm": checkbox},
    )

    tag_manager.update_master_tag_option_states(app)
    assert checkbox.states == {"alternate"}

    tags[1].enabled_alarm = True
    tag_manager.update_master_tag_option_states(app)
    assert checkbox.states == {"selected"}

    tags[0].enabled_alarm = tags[1].enabled_alarm = False
    tag_manager.update_master_tag_option_states(app)
    assert checkbox.states == set()


def test_individual_tag_toggle_updates_master_without_generating_signals():
    checkbox = _MasterCheckbox()
    modified = []
    tag = TagDefinition("A", "BOOL", "Input", "DBX0.0", enabled_sim=False)
    app = SimpleNamespace(
        tags=[tag],
        tag_master_checkboxes={"enabled_sim": checkbox},
        mark_project_modified=lambda: modified.append(True),
        generate_signals=lambda: (_ for _ in ()).throw(
            AssertionError("an individual option toggle must not generate signals")
        ),
    )

    tag_manager.set_tag_flag(app, tag, "enabled_sim", True)

    assert tag.enabled_sim is True
    assert checkbox.states == {"selected"}
    assert modified == [True]
