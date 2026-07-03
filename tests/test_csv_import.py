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
