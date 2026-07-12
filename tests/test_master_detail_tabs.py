from types import SimpleNamespace

from core.tag_model import TagDefinition
from core.tag_runtime import RuntimeTagCache
from ui import analog_tab, digital_tab


class Widget:
    def __init__(self, value=""):
        self.value = value

    def get(self): return self.value
    def set(self, value): self.value = value
    def configure(self, **kwargs): self.__dict__.update(kwargs)
    def delete(self, *_args): self.value = ""
    def insert(self, *_args): self.value = _args[-1]


class Table:
    def __init__(self):
        self.rows = []
        self.selected = ()

    def delete(self, *items): self.rows.clear()
    def get_children(self): return tuple(range(len(self.rows)))
    def insert(self, *_args, values=()):
        self.rows.append(tuple(values)); return len(self.rows) - 1
    def selection(self): return self.selected
    def selection_set(self, item): self.selected = (item,)
    def index(self, item): return int(item)
    def item(self, item, option=None, **kwargs):
        if "values" in kwargs: self.rows[int(item)] = tuple(kwargs["values"])
        return self.rows[int(item)] if option == "values" else {"values": self.rows[int(item)]}
    def winfo_exists(self): return True


def common_app(kind, tags, size):
    prefix = "digital" if kind == "digital" else "analog"
    app = SimpleNamespace(
        tags=tags, tag_runtime=RuntimeTagCache(), is_closing=False,
        is_rebuilding=False, _dirty_tabs={"Entradas Digitais", "Entradas Analógicas"},
        digital_controls=[], digital_tags=[], digital_states={},
        analog_controls=[], analog_tags=[], analog_profile_running={},
        analog_profile_directions={}, _pending_jobs=set(),
    )
    setattr(app, f"{prefix}_page", 0)
    setattr(app, f"{prefix}_page_size_menu", Widget(str(size)))
    setattr(app, f"{prefix}_previous_button", Widget())
    setattr(app, f"{prefix}_next_button", Widget())
    setattr(app, f"{prefix}_loading_label", Widget())
    setattr(app, f"_{prefix}_after_jobs", set())
    setattr(app, f"_{prefix}_rebuilding", False)
    setattr(app, f"{prefix}_table", Table())
    setattr(app, f"_{prefix}_table_tags", [])
    setattr(app, f"_{prefix}_selected_tag_name", None)
    app.cancel_job = lambda _job: None
    app.brand_menu = SimpleNamespace(get=lambda: "Simulator")
    return app


def test_1000_digital_tags_create_no_row_buttons(monkeypatch):
    tags = [TagDefinition(f"D{i}", "BOOL", "Input", f"M{i}.0", True) for i in range(1000)]
    app = common_app("digital", tags, 50)
    app.digital_editor_title = Widget()
    app.digital_editor_mode = Widget("Toggle")
    app.digital_editor_pulse = Widget("500")
    app.digital_editor_button = Widget()
    app.digital_editor_value = Widget()
    app.digital_action = lambda _index: None
    monkeypatch.setattr(digital_tab, "create_digital_row_widgets", lambda _app: (_ for _ in ()).throw(AssertionError("row button created")))
    monkeypatch.setattr("ui.tag_manager.get_input_bool_tags", lambda _app: tags)

    editor_button = app.digital_editor_button
    digital_tab.refresh_digital_visible_rows(app)
    app.digital_page = 1
    digital_tab.refresh_digital_visible_rows(app)

    assert len(app.digital_table.rows) == 50
    assert app.digital_editor_button is editor_button


def test_1000_analog_tags_create_no_row_sliders_and_reuse_editor(monkeypatch):
    tags = [TagDefinition(f"A{i}", "REAL", "Input", f"DBD{i * 4}", True) for i in range(1000)]
    app = common_app("analog", tags, 25)
    app.analog_search_entry = Widget("")
    app.analog_editor = {"identity": object()}
    bound = []
    monkeypatch.setattr(analog_tab, "create_analog_row_widgets", lambda _app: (_ for _ in ()).throw(AssertionError("row slider created")))
    monkeypatch.setattr(analog_tab, "bind_analog_row", lambda _app, row, index, tag: bound.append((row, tag.name)))
    monkeypatch.setattr("ui.tag_manager.get_input_analog_tags", lambda _app: tags)

    editor = app.analog_editor
    analog_tab.refresh_analog_visible_rows(app)
    app.analog_table.selection_set(1)
    analog_tab._bind_selected_analog(app)

    assert len(app.analog_table.rows) == 25
    assert app.analog_editor is editor
    assert bound[-1] == (editor, "A1")
