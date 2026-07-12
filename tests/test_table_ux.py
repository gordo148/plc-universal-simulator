from types import SimpleNamespace

from core.tag_model import TagDefinition
from ui import analog_tab, digital_tab
from ui import project_config
from ui.table_utils import filter_tags, move_selection, page_tags, sort_tags


TAGS = [
    TagDefinition("Valve10", "BOOL", "Input", "M10.0", True),
    TagDefinition("Pump2", "BOOL", "Input", "M2.0", True),
    TagDefinition("Level", "REAL", "Input", "DBD4", True),
]


def test_search_matches_name_address_and_type():
    assert [tag.name for tag in filter_tags(TAGS, "pump")] == ["Pump2"]
    assert [tag.name for tag in filter_tags(TAGS, "m10") ] == ["Valve10"]
    assert [tag.name for tag in filter_tags(TAGS, "real")] == ["Level"]


def test_sort_is_natural_and_toggles_direction():
    ascending = sort_tags(TAGS[:2], "name")
    descending = sort_tags(TAGS[:2], "name", descending=True)
    assert [tag.name for tag in ascending] == ["Pump2", "Valve10"]
    assert descending == list(reversed(ascending))


def test_all_page_size_keeps_one_table_model_page():
    page, count, start, visible = page_tags(range(5000), 20, "All")
    assert (page, count, start, len(visible)) == (0, 1, 0, 5000)


class KeyboardTable:
    def __init__(self): self.selected = (1,)
    def get_children(self): return (0, 1, 2, 3)
    def selection(self): return self.selected
    def index(self, item): return item
    def selection_set(self, item): self.selected = (item,)
    def focus(self, _item): pass
    def see(self, _item): pass
    def cget(self, _name): return 2


def test_keyboard_navigation_supports_arrows_pages_home_end():
    table = KeyboardTable()
    move_selection(table, "Down")
    assert table.selected == (2,)
    move_selection(table, "Home")
    assert table.selected == (0,)
    move_selection(table, "End")
    assert table.selected == (3,)
    move_selection(table, "Prior")
    assert table.selected == (1,)


def test_digital_space_and_double_click_reuse_editor_action():
    calls = []
    app = SimpleNamespace(digital_tags=[TAGS[0]], digital_action=lambda index: calls.append(index))
    assert digital_tab.handle_digital_key(app, SimpleNamespace(keysym="space")) == "break"
    digital_tab._digital_editor_action(app)
    assert calls == [0, 0]


def test_analog_double_click_focuses_existing_numeric_editor():
    calls = []
    entry = SimpleNamespace(
        focus_set=lambda: calls.append("focus"),
        select_range=lambda start, end: calls.append((start, end)),
    )
    app = SimpleNamespace(analog_tags=[TAGS[2]], analog_editor={"numeric_entry": entry})
    analog_tab._focus_analog_value(app)
    assert calls == ["focus", (0, "end")]


def test_context_menu_copy_payload_uses_selected_tag(monkeypatch):
    commands = {}
    class Menu:
        def __init__(self, *_args, **_kwargs): pass
        def add_command(self, label, command): commands[label] = command
        def add_separator(self): pass
        def tk_popup(self, *_args): pass
    class Table:
        def identify_row(self, _y): return 0
        def selection_set(self, _row): pass
        def selection(self): return (0,)
        def index(self, _row): return 0
    copied = []
    monkeypatch.setattr(digital_tab, "Menu", Menu)
    monkeypatch.setattr(digital_tab, "_bind_selected_digital", lambda _app: None)
    monkeypatch.setattr(digital_tab, "copy_text", lambda _widget, text: copied.append(text))
    app = SimpleNamespace(digital_table=Table(), _digital_table_tags=[TAGS[0]])
    digital_tab.show_digital_context_menu(app, SimpleNamespace(y=1, x_root=1, y_root=1))
    commands["Copy Full Tag"]()
    assert copied == ["Valve10\tM10.0\tBOOL"]


def test_project_ui_state_restores_search_sort_page_selection_and_tab(monkeypatch):
    class Entry:
        def __init__(self): self.value = ""
        def delete(self, *_args): self.value = ""
        def insert(self, _index, value): self.value = value
    class MenuWidget:
        def __init__(self): self.value = "50"
        def set(self, value): self.value = value
    class Tabs:
        def set(self, value): self.value = value
    refreshed = []
    monkeypatch.setattr(digital_tab, "refresh_digital_tab", lambda app, reset_page=False: refreshed.append("digital"))
    monkeypatch.setattr(analog_tab, "refresh_analog_tab", lambda app, reset_page=False: refreshed.append("analog"))
    # Imports inside the restore helper resolve module attributes.
    app = SimpleNamespace(
        digital_search_entry=Entry(), analog_search_entry=Entry(),
        digital_page_size_menu=MenuWidget(), analog_page_size_menu=MenuWidget(),
        tabs=Tabs(),
    )
    state = {
        "selected_tab": "Entradas Analógicas",
        "digital": {"search":"pump", "page_size":"250", "sort_column":"address", "sort_descending":True, "selected_row":"D4"},
        "analog": {"search":"real", "page_size":"All", "sort_column":"value", "sort_descending":False, "selected_row":"A7"},
    }
    project_config._restore_simulation_ui_state(app, state)
    assert app.digital_search_entry.value == "pump"
    assert app.analog_page_size_menu.value == "All"
    assert app._digital_selected_tag_name == "D4"
    assert app._analog_sort_column == "value"
    assert app.tabs.value == "Entradas Analógicas"
    assert refreshed == ["digital", "analog"]
