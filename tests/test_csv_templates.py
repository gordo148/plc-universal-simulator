import csv
from pathlib import Path

from ui.tag_manager import TAG_CSV_FIELDS


TEMPLATE_NAMES = [
    "universal_tags_template.csv",
    "siemens_tags_template.csv",
    "schneider_tags_template.csv",
    "rockwell_tags_template.csv",
    "omron_tags_template.csv",
    "modbus_tcp_tags_template.csv",
]


def test_csv_templates_exist_and_have_required_columns():
    templates_dir = Path(__file__).parent.parent / "templates"

    for template_name in TEMPLATE_NAMES:
        template_path = templates_dir / template_name
        assert template_path.is_file(), f"Template em falta: {template_name}"

        with template_path.open(newline="", encoding="utf-8") as template_file:
            reader = csv.DictReader(template_file)
            assert reader.fieldnames == TAG_CSV_FIELDS


def test_universal_template_contains_required_examples():
    template_path = (
        Path(__file__).parent.parent
        / "templates"
        / "universal_tags_template.csv"
    )
    with template_path.open(newline="", encoding="utf-8") as template_file:
        rows = list(csv.DictReader(template_file))

    assert [(row["data_type"], row["direction"]) for row in rows] == [
        ("BOOL", "Input"),
        ("INT", "Input"),
        ("REAL", "Input"),
        ("BOOL", "Feedback"),
        ("INT", "Feedback"),
        ("REAL", "Feedback"),
        ("REAL", "Internal"),
    ]
    assert rows[-1]["name"] == "PID_OUT"
