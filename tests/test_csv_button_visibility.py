from types import SimpleNamespace

import pytest

from ui.tag_manager import update_csv_button_visibility


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class Button:
    def __init__(self):
        self.visible = True

    def pack(self, **_options):
        self.visible = True

    def pack_forget(self):
        self.visible = False


@pytest.mark.parametrize(
    ("brand", "tia_visible", "schneider_visible"),
    [
        ("Siemens", True, False),
        ("Schneider", False, True),
        ("Rockwell", False, False),
        ("Omron", False, False),
        ("Modbus TCP", False, False),
        ("Simulator", False, False),
    ],
)
def test_csv_button_visibility_follows_selected_brand(
    brand,
    tia_visible,
    schneider_visible,
):
    app = SimpleNamespace(
        brand_menu=Value(brand),
        tag_import_csv_button=Button(),
        tag_import_tia_csv_button=Button(),
        tag_import_schneider_csv_button=Button(),
        tag_export_csv_button=Button(),
        tag_export_template_csv_button=Button(),
    )

    update_csv_button_visibility(app)

    assert app.tag_import_csv_button.visible is True
    assert app.tag_import_tia_csv_button.visible is tia_visible
    assert app.tag_import_schneider_csv_button.visible is schneider_visible
    assert app.tag_export_csv_button.visible is True
    assert app.tag_export_template_csv_button.visible is True
