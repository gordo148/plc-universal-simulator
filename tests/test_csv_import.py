from types import SimpleNamespace

import pytest

from core.tag_model import TagDefinition
from ui import tag_manager


CSV_HEADER = (
    "name,data_type,direction,address,enabled_sim,enabled_trend,"
    "enabled_alarm,enabled_dashboard\n"
)


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


def test_rockwell_csv_preserves_symbolic_tag_case(tmp_path):
    path = tmp_path / "rockwell.csv"
    path.write_text(
        CSV_HEADER + "Tank,REAL,Input,Tank_Level,1,1,0,0\n",
        encoding="utf-8",
    )

    tags = tag_manager.read_tags_csv(path, "Rockwell")

    assert tags[0].address == "Tank_Level"
