from types import SimpleNamespace

from core.dashboard_model import (
    COLUMN_KEYS,
    COMPACT_COLUMNS,
    DEFAULT_VISIBLE_COLUMNS,
    clamp_column_width,
    dashboard_statistics,
    default_dashboard_preferences,
    filter_dashboard_population,
    move_visible_column,
    normalize_dashboard_preferences,
    ordered_visible_columns,
    set_column_visibility,
    sort_dashboard_population,
    calculate_auto_fit_width,
)
from core.tag_model import TagDefinition
from core.tag_runtime import RuntimeTagCache, RuntimeValueSource
from core.connection_state import ConnectionState
from services.settings_service import ApplicationSettings
from ui import dashboard_tab, project_config


def tags_fixture():
    return [
        TagDefinition("Tag10", "INT", "Input", "%MW10", True, False, True, True, "Pressão São"),
        TagDefinition("Tag2", "BOOL", "Input", "%M2", False, True, False, True, "Motor"),
        TagDefinition("Real", "REAL", "Input", "%MW20", True, True, True, True, ""),
    ]


def test_dashboard_preference_defaults_are_versioned_and_usable():
    preferences = default_dashboard_preferences()
    assert preferences["version"] == 1
    assert tuple(preferences["full_layout"]["visible"]) == DEFAULT_VISIBLE_COLUMNS
    assert "name" in ordered_visible_columns(preferences)


def test_invalid_preferences_recover_fields_independently():
    preferences = normalize_dashboard_preferences({
        "version": 999,
        "full_layout": {
            "visible": ["unknown", "value"],
            "order": ["value", "value", "unknown"],
            "widths": {"value": 99999, "name": "wide"},
        },
        "sort": {"column": "comment", "descending": True},
        "splitter": 99,
    })
    assert preferences["full_layout"]["visible"] == ["value", "name"]
    assert set(preferences["full_layout"]["order"]) == set(COLUMN_KEYS)
    assert preferences["full_layout"]["widths"]["value"] == clamp_column_width("value", 99999)
    assert preferences["sort"] == {"column": "name", "descending": True}
    assert preferences["splitter"] == 0.85


def test_legacy_dashboard_preference_draft_is_migrated():
    preferences = normalize_dashboard_preferences({
        "visible_columns": ["name", "comment"],
        "column_order": ["comment", "name"],
        "column_widths": {"comment": 444},
        "compact_view": True,
        "sort_column": "address",
        "sort_descending": True,
    })
    assert preferences["compact"] is True
    assert preferences["full_layout"]["visible"] == ["name", "comment"]
    assert preferences["full_layout"]["order"][:2] == ["comment", "name"]
    assert preferences["full_layout"]["widths"]["comment"] == 444
    assert preferences["sort"] == {"column": "address", "descending": True}


def test_visibility_name_protection_compact_and_reorder_round_trip():
    preferences = default_dashboard_preferences()
    preferences = set_column_visibility(preferences, "address", True)
    preferences = set_column_visibility(preferences, "name", False)
    assert "name" in ordered_visible_columns(preferences)
    before = ordered_visible_columns(preferences)
    preferences["compact"] = True
    assert ordered_visible_columns(preferences) == COMPACT_COLUMNS
    assert ordered_visible_columns(preferences) == ("status", "name", "value", "comment")
    preferences["compact"] = False
    assert ordered_visible_columns(preferences) == before
    moved = move_visible_column(preferences, "value", -1)
    assert ordered_visible_columns(moved) != before


def test_search_filters_are_unicode_and_composable():
    tags = tags_fixture()
    runtime = RuntimeTagCache(); runtime.sync(tags)
    runtime.update("Tag10", 10, RuntimeValueSource.PLC)
    assert [tag.name for tag in filter_dashboard_population(tags, "são", runtime=runtime)] == ["Tag10"]
    assert [tag.name for tag in filter_dashboard_population(tags, filters={"statuses":["GOOD"], "features":["simulation", "alarm"], "types":["INT"]}, runtime=runtime)] == ["Tag10"]
    assert len(filter_dashboard_population(tags, filters={"statuses":["GOOD", "BAD"]}, runtime=runtime)) == 3


def test_value_sort_is_numeric_natural_and_missing_last_in_both_directions():
    tags = tags_fixture()
    runtime = RuntimeTagCache(); runtime.sync(tags)
    runtime.update("Tag10", 10); runtime.update("Tag2", 2)
    assert [tag.name for tag in sort_dashboard_population(tags, "name", runtime=runtime)][:2] == ["Real", "Tag2"]
    assert [tag.name for tag in sort_dashboard_population(tags, "value", runtime=runtime)] == ["Tag2", "Tag10", "Real"]
    assert [tag.name for tag in sort_dashboard_population(tags, "value", True, runtime)] == ["Tag10", "Tag2", "Real"]


def test_statistics_use_complete_dashboard_population_and_runtime_quality():
    tags = tags_fixture()
    runtime = RuntimeTagCache(); runtime.sync(tags); runtime.update("Tag2", False)
    assert dashboard_statistics(tags, runtime) == {
        "total": 3, "good": 1, "bad": 2,
        "simulation": 2, "trend": 2, "alarm": 2,
    }


class LayoutTable:
    def __init__(self):
        self.displaycolumns = (); self.rows = {"row": {"name":"Long name", "comment":"x"*1000}}
        self.widths = {key: 100 for key in COLUMN_KEYS}; self.headings = {}; self.selected=("row",)
    def configure(self, **kwargs): self.displaycolumns = kwargs.get("displaycolumns",self.displaycolumns)
    def column(self,key,option=None,**kwargs):
        if "width" in kwargs:self.widths[key]=kwargs["width"]
        return self.widths[key] if option=="width" else {"width":self.widths[key]}
    def heading(self,key,**kwargs): self.headings[key]=kwargs
    def get_children(self): return tuple(self.rows)
    def set(self,item,column): return self.rows[item].get(column,"")
    def selection(self): return self.selected


class Recorder:
    def __init__(self): self.configurations=[]
    def configure(self,**kwargs): self.configurations.append(kwargs)


def layout_app():
    return SimpleNamespace(
        settings=ApplicationSettings(), dashboard_tag_table=LayoutTable(),
        dashboard_compact_button=Recorder(),
    )


def test_column_layout_uses_displaycolumns_without_mutating_rows_or_selection():
    app=layout_app(); before_rows=dict(app.dashboard_tag_table.rows); before_selection=app.dashboard_tag_table.selection()
    dashboard_tab.apply_dashboard_column_layout(app)
    assert app.dashboard_tag_table.displaycolumns == DEFAULT_VISIBLE_COLUMNS
    assert app.dashboard_tag_table.rows == before_rows
    assert app.dashboard_tag_table.selection() == before_selection


def test_compact_view_preserves_and_restores_exact_full_layout():
    app=layout_app(); preferences=app.settings.ui_preferences["dashboard_ui"]
    preferences["full_layout"]["visible"]=["name","comment","value"]
    preferences["full_layout"]["order"]=["comment","value","name"]+[key for key in COLUMN_KEYS if key not in ("comment","value","name")]
    before=ordered_visible_columns(preferences)
    dashboard_tab.toggle_dashboard_compact_view(app)
    assert app.dashboard_tag_table.displaycolumns == COMPACT_COLUMNS
    assert app.dashboard_tag_table.displaycolumns == ("status", "name", "value", "comment")
    dashboard_tab.toggle_dashboard_compact_view(app)
    assert app.dashboard_tag_table.displaycolumns == before


def test_compact_comment_cells_preserve_filled_and_empty_model_values():
    tags=[
        TagDefinition("WithComment","BOOL","Input","M0",enabled_dashboard=True,comment="Motor principal"),
        TagDefinition("WithoutComment","BOOL","Input","M1",enabled_dashboard=True,comment=""),
    ]
    displayed=[getattr(tag,"comment","") or "" for tag in tags]
    assert displayed == ["Motor principal", ""]
    assert "comment" in COMPACT_COLUMNS


def test_auto_fit_is_bounded_and_clamped_for_long_comments():
    calls=[]
    width=calculate_auto_fit_width("Comment",("x"*1000 for _ in range(5000)),lambda text:calls.append(text) or len(text)*8,100,600)
    assert width == 600
    assert len(calls) == 501


def test_sort_indicator_is_present_only_on_active_heading():
    table=LayoutTable()
    dashboard_tab.configure_dashboard_headings(table,lambda _column:None,"value",True)
    assert table.headings["value"]["text"].endswith("▼")
    assert all("▲" not in options["text"] and "▼" not in options["text"] for key,options in table.headings.items() if key!="value")


def test_project_serialization_never_contains_dashboard_ui_preferences(project_app):
    project_app.settings=ApplicationSettings(); project_app.settings.ui_preferences["dashboard_ui"]["compact"]=True
    payload=project_config.build_project_data(project_app)
    assert "dashboard_ui" not in repr(payload)


def test_project_reset_clears_identity_mapping_but_preserves_layout():
    class Rows:
        def __init__(self):self.deleted=[]
        def get_children(self):return ("old",)
        def delete(self,*items):self.deleted.extend(items)
    preferences=ApplicationSettings().ui_preferences["dashboard_ui"]
    app=SimpleNamespace(settings=SimpleNamespace(ui_preferences={"dashboard_ui":preferences}),dashboard_tag_table=Rows(),_dashboard_generation=2,_dashboard_selected_name="SameName",_dashboard_row_ids={"SameName":"old"},_dashboard_row_values={"SameName":("old",)},_dashboard_visible_tags=[],dashboard_detail_labels={})
    dashboard_tab.reset_dashboard_project_state(app)
    assert app._dashboard_generation == 3
    assert app._dashboard_selected_name is None
    assert app._dashboard_row_ids == {}
    assert app.settings.ui_preferences["dashboard_ui"] is preferences


def test_5000_tag_model_operations_remain_bounded():
    import time
    tags=[TagDefinition(f"T{i}",("BOOL","INT","REAL")[i%3],"Input",f"A{i}",enabled_dashboard=True,comment=f"Comment {i}") for i in range(5000)]
    runtime=RuntimeTagCache();runtime.sync(tags)
    started=time.perf_counter()
    filtered=filter_dashboard_population(tags,"comment 4999",{"types":["INT","REAL"]},runtime)
    ordered=sort_dashboard_population(tags,"name",False,runtime)
    stats=dashboard_statistics(tags,runtime)
    assert (time.perf_counter()-started)*1000 < 250
    assert [tag.name for tag in filtered] == ["T4999"]
    assert len(ordered)==stats["total"]==5000


def test_selected_tag_static_and_dynamic_refresh_paths_are_separate():
    tag=TagDefinition("Zero","INT","Input","%MW0",True,True,True,True,"Comentário")
    runtime=RuntimeTagCache();runtime.sync([tag]);runtime.update("Zero",0)
    fields=("Name","Comment","Address","Data Type","Direction","Simulation","Trend","Alarm","Dashboard","Effective value","PLC value","Simulated value","Source","Quality","Last update")
    labels={field:Recorder() for field in fields}; indicator=Recorder()
    state=ConnectionState();state.set_brand("Simulator")
    app=SimpleNamespace(tags=[tag],tag_runtime=runtime,connection_state=state,dashboard_detail_labels=labels,dashboard_detail_indicator=indicator,_plc_values={},_simulated_values={})
    dashboard_tab.refresh_dashboard_detail_static(app,tag)
    dashboard_tab.refresh_dashboard_detail_dynamic(app,tag)
    static_calls=len(labels["Name"].configurations); dynamic_calls=len(labels["Effective value"].configurations)
    dashboard_tab.refresh_dashboard_detail_static(app,tag)
    dashboard_tab.refresh_dashboard_detail_dynamic(app,tag)
    assert len(labels["Name"].configurations)==static_calls
    assert len(labels["Effective value"].configurations)==dynamic_calls
    assert labels["Effective value"].configurations[-1]["text"].endswith(": 0")
    runtime.update("Zero",1)
    dashboard_tab.refresh_dashboard_detail_dynamic(app,tag)
    assert len(labels["Name"].configurations)==static_calls
    assert len(labels["Effective value"].configurations)==dynamic_calls+1
