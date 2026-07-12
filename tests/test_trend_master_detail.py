from pathlib import Path
from types import SimpleNamespace

from core.tag_model import TagDefinition
from ui import project_config, trend_tab


class Value:
    def __init__(self, value): self.value = value
    def get(self): return self.value


def test_trends_source_has_no_per_tag_checkbox_loop():
    source = Path(trend_tab.__file__).read_text(encoding="utf-8")
    assert "trend_curve_widgets" not in source
    assert "app.trend_tag_vars[tag.name]" not in source
    assert "CTkCheckBox(app.trend_selector_frame" not in source


def test_filter_search_and_type_work_together():
    tags = [TagDefinition("Pump Speed", "REAL", "Input", "DBD20", enabled_trend=True), TagDefinition("Pump Run", "BOOL", "Input", "DBX0.0")]
    app = SimpleNamespace(tags=tags, trend_search_entry=Value("pump"), trend_filter_menu=Value("REAL"), trend_visible_tags={"Pump Speed"}, _trend_sort_column="name", _trend_sort_descending=False, tag_runtime=None)
    assert trend_tab._filtered_trend_tags(app) == [tags[0]]
    app.trend_search_entry.value = "dbx"
    app.trend_filter_menu.value = "BOOL"
    assert trend_tab._filtered_trend_tags(app) == [tags[1]]


def test_enabled_visible_and_hidden_filters():
    enabled = TagDefinition("Enabled", "INT", "Input", "DBW0", enabled_trend=True)
    disabled = TagDefinition("Disabled", "INT", "Input", "DBW2")
    app = SimpleNamespace(tags=[enabled, disabled], trend_search_entry=Value(""), trend_filter_menu=Value("Enabled"), trend_visible_tags={enabled.name}, _trend_sort_column="name", _trend_sort_descending=False, tag_runtime=None)
    assert trend_tab._filtered_trend_tags(app) == [enabled]
    app.trend_filter_menu.value = "Disabled"; assert trend_tab._filtered_trend_tags(app) == [disabled]
    app.trend_filter_menu.value = "Visible"; assert trend_tab._filtered_trend_tags(app) == [enabled]
    app.trend_filter_menu.value = "Hidden"; assert trend_tab._filtered_trend_tags(app) == [disabled]


def test_project_build_uses_lightweight_visible_set(project_app):
    project_app.tags[0].enabled_trend = True
    project_app.trend_visible_tags = {project_app.tags[0].name}
    project = project_config.build_project_data(project_app)
    assert project["trends"]["enabled_tags"] == [project_app.tags[0].name]
    assert project["trends"]["selected_curves"] == [project_app.tags[0].name]


def test_default_config_is_reused_without_tk_variable():
    tag = TagDefinition("Speed", "REAL", "Input", "DBD0", enabled_trend=True)
    app = SimpleNamespace(_trend_configs={})
    first = trend_tab._trend_config(app, tag); second = trend_tab._trend_config(app, tag)
    assert first is second
    assert first["visible"] is True


def test_hidden_config_follows_lightweight_visible_set():
    tag = TagDefinition("Speed", "REAL", "Input", "DBD0", enabled_trend=True)
    app = SimpleNamespace(_trend_configs={}, trend_visible_tags=set())
    assert trend_tab._trend_config(app, tag)["visible"] is False


def test_start_and_stop_trend_reuse_existing_engine(monkeypatch):
    updates = []
    status = SimpleNamespace(configure=lambda **values: updates.append(values))
    app = SimpleNamespace(trend_running=False, trend_status=status)
    monkeypatch.setattr(trend_tab, "update_trend", lambda current: updates.append(current))
    monkeypatch.setattr(trend_tab, "widget_exists", lambda _widget: True)
    trend_tab.start_trend(app)
    assert app.trend_running is True
    assert updates[-1] is app
    trend_tab.stop_trend(app)
    assert app.trend_running is False


def test_refresh_does_not_recreate_chart_or_editor():
    source = Path(trend_tab.__file__).read_text(encoding="utf-8")
    refresh_source = source.split("def refresh_trend_selectors", 1)[1].split("def update_trend_table_values", 1)[0]
    assert "Figure(" not in refresh_source
    assert "CTkFrame(" not in refresh_source
    assert "CTkCheckBox(" not in refresh_source


def test_cancel_trend_callbacks_cancels_each_job_once():
    cancelled = []
    app = SimpleNamespace(_trend_search_debounce_job="search", _trend_after_jobs={"sample"}, cancel_job=cancelled.append)
    trend_tab.cancel_trend_callbacks(app)
    trend_tab.cancel_trend_callbacks(app)
    assert cancelled == ["search", "sample"]
