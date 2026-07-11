import time
from types import SimpleNamespace

from core.tag_model import TagDefinition
from ui import tag_manager


def tags():
    return [
        TagDefinition("StartPump", "BOOL", "Input", "DBX0.0"),
        TagDefinition("TankLevel", "REAL", "Feedback", "DBD20"),
        TagDefinition("MotorSpeed", "INT", "Output", "DBW30"),
    ]


def test_tag_search_matches_all_fields_case_insensitively():
    source = tags()
    assert [tag.name for tag in tag_manager.filter_tag_collection(source, "start")] == ["StartPump"]
    assert [tag.name for tag in tag_manager.filter_tag_collection(source, "dbd20")] == ["TankLevel"]
    assert [tag.name for tag in tag_manager.filter_tag_collection(source, "REAL")] == ["TankLevel"]
    assert [tag.name for tag in tag_manager.filter_tag_collection(source, "output")] == ["MotorSpeed"]
    assert tag_manager.filter_tag_collection(source, "") == source
    assert source == tags()  # filtering never mutates the full collection


def test_5000_tag_filtering_is_under_budget():
    source = [TagDefinition(f"Tag{i}", "BOOL", "Input", f"DBX{i}.0") for i in range(5000)]
    started = time.perf_counter()
    result = tag_manager.filter_tag_collection(source, "tag4999")
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert [tag.name for tag in result] == ["Tag4999"]
    assert elapsed_ms < 50


class Entry:
    def __init__(self, value=""): self.value = value
    def get(self): return self.value
    def delete(self, *_args): self.value = ""
    def focus_set(self): pass


class Label:
    def configure(self, **kwargs): self.__dict__.update(kwargs)


class Table:
    def __init__(self): self.rows, self.selected = {}, ()
    def get_children(self): return tuple(self.rows)
    def delete(self, *items):
        for item in items: self.rows.pop(item, None)
    def tag_configure(self, *_args, **_kwargs): pass
    def insert(self, _parent, _where, iid, values, tags): self.rows[iid] = values
    def selection(self): return self.selected
    def selection_set(self, item): self.selected = (item,)
    def focus(self, _item): pass
    def see(self, _item): pass


def app_for_refresh(query=""):
    app = SimpleNamespace(
        tags=tags(), tag_table=Table(), tag_search_entry=Entry(query),
        tag_search_count_label=Label(),
        brand_menu=SimpleNamespace(get=lambda: "Siemens"),
    )
    return app


def test_filter_count_and_selection_preservation(monkeypatch):
    monkeypatch.setattr(tag_manager, "validate_tag_address", lambda *_args: (True, ""))
    app = app_for_refresh("")
    tag_manager.refresh_tag_table(app, view_only=True)
    app.tag_table.selection_set("1")
    app.tag_search_entry.value = "level"
    tag_manager.refresh_tag_table(app, view_only=True)
    assert app.tag_table.selection() == ("1",)
    assert app.tag_search_count_label.text == "Showing 1 of 3 tags"

    app.tag_search_entry.value = "motor"
    tag_manager.refresh_tag_table(app, view_only=True)
    assert app.tag_table.selection() == ("2",)
    app.tag_search_entry.value = ""
    tag_manager.refresh_tag_table(app, view_only=True)
    assert app.tag_table.selection() == ("1",)
    assert app.tag_search_count_label.text == "3 tags"


def test_clear_search_refreshes_only_table_view(monkeypatch):
    calls = []
    app = SimpleNamespace(tag_search_entry=Entry("pump"))
    monkeypatch.setattr(tag_manager, "refresh_tag_table", lambda _app, view_only=False: calls.append(view_only))
    tag_manager.clear_tag_search(app)
    assert app.tag_search_entry.value == ""
    assert calls == [True]
