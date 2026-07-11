from types import SimpleNamespace

import pytest

from core.tag_model import TagDefinition
from core.tag_runtime import RuntimeTagCache, RuntimeValueSource
from ui import digital_tab, main_window
from ui.scrollable_frame import normalized_scroll_units, safe_scrollbar_set


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        (SimpleNamespace(num=4, delta=0), -1),
        (SimpleNamespace(num=5, delta=0), 1),
        (SimpleNamespace(delta=120), -1),
        (SimpleNamespace(delta=-240), 2),
        (SimpleNamespace(delta=100000), -3),
        (SimpleNamespace(delta=-100000), 3),
        (SimpleNamespace(delta=0), 0),
    ],
)
def test_normalized_wheel_events(event, expected):
    assert normalized_scroll_units(event) == expected


def test_page_slice_clamps_page_and_supports_configured_sizes():
    tags = list(range(5000))
    page, pages, start, visible = digital_tab.page_slice(tags, 999, 100)

    assert (page, pages, start) == (49, 50, 4900)
    assert visible == list(range(4900, 5000))
    assert len(digital_tab.page_slice(tags, 0, 25)[3]) == 25


def test_safe_scrollbar_set_ignores_destroyed_scrollbar():
    class DestroyedScrollbar:
        def winfo_exists(self):
            return 0

        def set(self, *_args):
            raise AssertionError("destroyed scrollbar must not be called")

    safe_scrollbar_set(DestroyedScrollbar(), "0.0", "1.0")


def test_tab_structure_creation_is_idempotent(monkeypatch):
    created = []

    class Widget:
        def __init__(self, *_args, **_kwargs):
            created.append(self)

        def pack(self, **_kwargs):
            pass

        def grid(self, **_kwargs):
            pass

        def bind(self, *_args, **_kwargs):
            pass

        def set(self, value):
            self.value = value

        def insert(self, *_args):
            pass

    for name in ("CTkFrame", "CTkLabel", "CTkEntry", "CTkOptionMenu", "CTkButton"):
        monkeypatch.setattr(digital_tab.ctk, name, Widget)
    class Table(Widget):
        def heading(self, *_args, **_kwargs): pass
        def column(self, *_args, **_kwargs): pass
        def configure(self, **_kwargs): pass
        def yview(self, *_args): pass
    monkeypatch.setattr(digital_tab.ttk, "Treeview", Table)
    monkeypatch.setattr(digital_tab.ttk, "Scrollbar", Table)

    app = SimpleNamespace(tab_digital=object())
    digital_tab.create_digital_tab_structure(app)
    structural_widgets = list(created)
    digital_tab.create_digital_tab_structure(app)

    assert created == structural_widgets
    assert app._digital_structure_initialized is True


def test_digital_page_render_is_batched_and_only_builds_visible_tags(monkeypatch):
    tags = [TagDefinition(f"D{i}", "BOOL", "Input", f"M{i}.0") for i in range(5000)]
    queue = []
    created = []

    class Scroll:
        def __init__(self):
            self.children = [SimpleNamespace(destroy=lambda: None)]

        def winfo_children(self):
            return self.children

    class Widget:
        def __init__(self, value="50"):
            self.value = value

        def get(self):
            return self.value

        def configure(self, **kwargs):
            self.__dict__.update(kwargs)

    app = SimpleNamespace(
        tags=tags, digital_page=1, digital_page_size_menu=Widget(),
        digital_scroll=Scroll(), digital_controls=[], digital_tags=[],
        digital_states={}, pending_pulse_callbacks={}, _digital_after_jobs=set(),
        _digital_rebuilding=False, _dirty_tabs={"Entradas Digitais"},
        digital_loading_label=Widget(), digital_previous_button=Widget(),
        digital_next_button=Widget(), is_closing=False,
    )
    app.cancel_job = lambda _job: None
    app.schedule_job = lambda _delay, callback: queue.append(callback) or callback
    app.clear_signal_frames = lambda: main_window.PLCSimulator.clear_signal_frames(app)
    monkeypatch.setattr("ui.tag_manager.get_input_bool_tags", lambda _app: tags)
    class Frame:
        def pack(self, **_kwargs): pass
        def pack_forget(self): pass

    monkeypatch.setattr(
        digital_tab, "create_digital_row_widgets",
        lambda _app: {"frame": Frame(), "current_tag_index": None, "tag": None},
    )
    monkeypatch.setattr(
        digital_tab, "bind_digital_row",
        lambda _app, row, index, tag: created.append((index, tag.name)),
    )

    digital_tab.refresh_digital_tab(app)
    while queue:
        queue.pop(0)()

    assert len(created) == 50
    assert created[0] == (0, "D50")
    assert created[-1] == (49, "D99")
    assert app.digital_loading_label.text.startswith("Page 2 of 100")


def test_runtime_poll_updates_visible_rows_only():
    calls = []
    cache = RuntimeTagCache()
    visible = [TagDefinition("D50", "BOOL", "Input", "M50.0")]
    cache.update("D50", True, RuntimeValueSource.PLC)
    cache.update("D1", True, RuntimeValueSource.PLC)
    app = SimpleNamespace(
        tag_runtime=cache, digital_tags=visible, analog_tags=[],
        update_digital_ui=lambda index, value: calls.append((index, value)),
    )

    main_window.PLCSimulator.update_runtime_widgets(app)

    assert calls == [(0, True)]


class PoolFrame:
    def __init__(self):
        self.visible = False
        self.destroy_calls = 0

    def pack(self, **_kwargs):
        self.visible = True

    def pack_forget(self):
        self.visible = False

    def destroy(self):
        self.destroy_calls += 1


class PoolWidget:
    def __init__(self, value="50"):
        self.value = value
        self.state = None
        self.text = ""

    def get(self):
        return self.value

    def configure(self, **kwargs):
        self.__dict__.update(kwargs)


def _drain(queue):
    while queue:
        queue.pop(0)()


def test_digital_pool_reuses_rows_for_page_size_and_page_changes(monkeypatch):
    tags = [TagDefinition(f"D{i}", "BOOL", "Input", f"M{i}.0") for i in range(200)]
    queue = []
    created = []

    def factory(_app):
        row = {
            "frame": PoolFrame(), "current_tag_index": None, "tag": None,
            "mode_menu": PoolWidget("Toggle"), "pulse_entry": PoolWidget("500"),
        }
        created.append(row)
        return row

    def bind(_app, row, index, tag):
        row["current_tag_index"] = index
        row["tag"] = tag
        # configure semantics replace the previous command instead of stacking it.
        row["command"] = lambda: tag.name
        _app.digital_states[index] = False

    app = SimpleNamespace(
        digital_page=0, digital_page_size_menu=PoolWidget("50"),
        digital_controls=[], digital_tags=[], digital_states={},
        digital_row_pool=[], _digital_after_jobs=set(), _digital_rebuilding=False,
        _dirty_tabs={"Entradas Digitais"}, digital_loading_label=PoolWidget(),
        digital_previous_button=PoolWidget(), digital_next_button=PoolWidget(),
    )
    app.cancel_job = lambda _job: None
    app.schedule_job = lambda _delay, callback: queue.append(callback) or callback
    monkeypatch.setattr("ui.tag_manager.get_input_bool_tags", lambda _app: tags)
    monkeypatch.setattr(digital_tab, "create_digital_row_widgets", factory)
    monkeypatch.setattr(digital_tab, "bind_digital_row", bind)

    digital_tab.refresh_digital_tab(app)
    _drain(queue)
    first_fifty = list(app.digital_row_pool)
    assert len(created) == 50
    assert all(row["frame"].visible for row in first_fifty)

    app.digital_page_size_menu.value = "25"
    digital_tab.refresh_digital_tab(app)
    assert app.digital_row_pool == first_fifty
    assert all(row["frame"].visible for row in first_fifty[:25])
    assert all(not row["frame"].visible for row in first_fifty[25:])
    assert all(row["frame"].destroy_calls == 0 for row in first_fifty)

    app.digital_page_size_menu.value = "50"
    digital_tab.refresh_digital_tab(app)
    assert app.digital_row_pool == first_fifty
    assert all(row["frame"].visible for row in first_fifty)

    app.digital_page_size_menu.value = "100"
    digital_tab.refresh_digital_tab(app)
    _drain(queue)
    assert len(app.digital_row_pool) == 100
    assert app.digital_row_pool[:50] == first_fifty
    assert len(created) == 100

    old_command = app.digital_row_pool[0]["command"]
    app.digital_page = 1
    digital_tab.refresh_digital_tab(app)
    assert app.digital_row_pool[0] is first_fifty[0]
    assert old_command() == "D0"
    assert app.digital_row_pool[0]["command"]() == "D100"
    assert app.digital_loading_label.text.startswith("Page 2 of 2")
    assert app.digital_previous_button.state == "normal"
    assert app.digital_next_button.state == "disabled"


def test_analog_pool_grows_only_when_page_size_increases(monkeypatch):
    from ui import analog_tab

    tags = [TagDefinition(f"A{i}", "REAL", "Input", f"DBD{i * 4}") for i in range(200)]
    queue = []
    created = []

    def factory(_app):
        row = {
            "frame": PoolFrame(), "current_tag_index": None, "tag": None,
            "interactive": False,
        }
        created.append(row)
        return row

    def bind(_app, row, index, tag):
        row["current_tag_index"] = index
        row["tag"] = tag
        row["slider_command"] = lambda _value=None: tag.name
        _app.analog_profile_directions[index] = 1

    app = SimpleNamespace(
        analog_page=0, analog_page_size_menu=PoolWidget("50"),
        analog_search_entry=PoolWidget(""), analog_controls=[], analog_tags=[],
        analog_row_pool=[], analog_profile_running={}, analog_profile_directions={},
        _analog_after_jobs=set(), _analog_rebuilding=False,
        _dirty_tabs={"Entradas Analógicas"}, analog_loading_label=PoolWidget(),
        analog_previous_button=PoolWidget(), analog_next_button=PoolWidget(),
        is_closing=False,
    )
    app.cancel_job = lambda _job: None
    app.schedule_job = lambda _delay, callback: queue.append(callback) or callback
    monkeypatch.setattr("ui.tag_manager.get_input_analog_tags", lambda _app: tags)
    monkeypatch.setattr(analog_tab, "create_analog_row_widgets", factory)
    monkeypatch.setattr(analog_tab, "bind_analog_row", bind)

    analog_tab.refresh_analog_tab(app)
    _drain(queue)
    first_fifty = list(app.analog_row_pool)
    assert len(created) == 50

    app.analog_page_size_menu.value = "25"
    analog_tab.refresh_analog_tab(app)
    _drain(queue)
    assert app.analog_row_pool == first_fifty
    assert sum(row["frame"].visible for row in first_fifty) == 25

    app.analog_page_size_menu.value = "50"
    analog_tab.refresh_analog_tab(app)
    _drain(queue)
    assert app.analog_row_pool == first_fifty

    app.analog_page_size_menu.value = "100"
    analog_tab.refresh_analog_tab(app)
    _drain(queue)
    assert len(created) == 100
    assert app.analog_row_pool[:50] == first_fifty
