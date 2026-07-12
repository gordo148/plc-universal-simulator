import time
from types import SimpleNamespace
from core.connection_state import ConnectionState

from core.tag_model import TagDefinition
from core.tag_runtime import RuntimeTagCache, RuntimeValueSource
from services.plc_service import PLCService
from ui import dashboard_tab


def make_tags(count=4):
    return [
        TagDefinition(
            f"T{i}", ("BOOL","INT","REAL")[i % 3], "Input", f"A{i}",
            enabled_sim=i % 2 == 0, enabled_trend=i == 1,
            enabled_alarm=i == 2, enabled_dashboard=i != 3,
        ) for i in range(count)
    ]


def test_summary_card_counts_and_online_offline_state():
    service=SimpleNamespace(
        is_connected=lambda:False,
        diagnostics_snapshot=lambda:{"read_error_count":0,"last_read_timestamp":None,"last_read_duration_ms":0},
    )
    app=SimpleNamespace(tags=make_tags(),plc_service=service,connection_state=ConnectionState(ip="10.0.0.1"),project_path=None)
    counts=dashboard_tab.dashboard_counts(app); values=dashboard_tab.dashboard_summary_values(app)
    assert counts == {"total":4,"simulation":2,"trends":1,"alarms":1,"dashboard":3}
    assert values["PLC"] == ("OFFLINE","red")
    service.is_connected=lambda:True
    assert dashboard_tab.dashboard_summary_values(app)["PLC"] == ("ONLINE","green")


def test_internal_simulator_endpoint():
    service=SimpleNamespace(is_connected=lambda:True,diagnostics_snapshot=lambda:{"read_error_count":0,"last_read_timestamp":None,"last_read_duration_ms":1.5})
    state=ConnectionState(); state.set_brand("Simulator")
    app=SimpleNamespace(tags=[],plc_service=service,connection_state=state,project_path=None)
    assert dashboard_tab.dashboard_summary_values(app)["Endpoint"][0] == "Internal Simulator"


def test_dashboard_filter_search_and_quick_filters():
    tags=make_tags()
    runtime=RuntimeTagCache();runtime.sync(tags);runtime.update("T0",True,RuntimeValueSource.PLC)
    assert [t.name for t in dashboard_tab.filter_dashboard_tags(tags,"a2")] == ["T2"]
    assert all(t.data_type=="BOOL" for t in dashboard_tab.filter_dashboard_tags(tags,"","BOOL"))
    assert [t.name for t in dashboard_tab.filter_dashboard_tags(tags,"","PLC source",runtime)] == ["T0"]


def test_alarm_summary_integration_and_empty_state():
    app=SimpleNamespace(alarms=[])
    assert dashboard_tab.dashboard_alarm_summary(app)["active"] == 0
    app.alarms=[{"source":"T1","type":"HIGH HIGH","active":True,"ack":False},{"source":"T2","type":"LOW","active":True,"ack":True}]
    summary=dashboard_tab.dashboard_alarm_summary(app)
    assert (summary["active"],summary["unacknowledged"],summary["high_priority"]) == (2,1,1)


def test_event_deque_is_bounded():
    app=SimpleNamespace()
    for index in range(100): dashboard_tab.record_dashboard_event(app,f"event {index}")
    assert len(app.dashboard_events) == dashboard_tab.EVENT_LIMIT
    assert app.dashboard_events[-1][2] == "event 99"


def test_dashboard_callback_cancellation():
    cancelled=[]
    app=SimpleNamespace(_dashboard_after_jobs={"a","b"},cancel_job=lambda job:cancelled.append(job))
    dashboard_tab.cancel_dashboard_callbacks(app)
    assert set(cancelled)=={"a","b"}
    assert app._dashboard_after_jobs==set()


def test_5000_tag_dashboard_filter_performance():
    tags=[TagDefinition(f"Tag{i}","BOOL","Input",f"M{i}",enabled_dashboard=i<1000) for i in range(5000)]
    enabled=[tag for tag in tags if tag.enabled_dashboard]
    started=time.perf_counter();result=dashboard_tab.filter_dashboard_tags(enabled,"tag999")
    assert (time.perf_counter()-started)*1000 < 100
    assert [tag.name for tag in result] == ["Tag999"]


def test_passive_plc_diagnostics_counts_reads_and_writes():
    class Driver:
        def is_connected(self):return True
        def read(self,*_args):return True
    service=PLCService(driver=Driver())
    service._brand="Unsupported" # read returns False without changing driver behavior
    service.read([])
    snapshot=service.diagnostics_snapshot()
    assert snapshot["read_error_count"] == 1
    assert snapshot["average_read_duration_ms"] >= 0


def test_double_click_navigation_preserves_digital_selection(monkeypatch):
    tag=TagDefinition("Start","BOOL","Input","M0",enabled_dashboard=True)
    calls=[]
    app=SimpleNamespace(
        _dashboard_selected_name="Start",tags=[tag],
        tabs=SimpleNamespace(set=lambda name:calls.append(name)),
    )
    monkeypatch.setattr("ui.digital_tab.refresh_digital_tab",lambda target:calls.append(target._digital_selected_tag_name))
    dashboard_tab.open_selected_dashboard_tag(app)
    assert app._digital_selected_tag_name == "Start"
    assert calls == ["Entradas Digitais","Start"]


def test_unchanged_table_signature_skips_tree_rebuild(monkeypatch):
    tag=TagDefinition("D","BOOL","Input","M0",enabled_dashboard=True)
    runtime=RuntimeTagCache();runtime.sync([tag])
    class Table:
        def __init__(self):self.rows=[];self.deleted=0;self.selected=()
        def get_children(self):return tuple(range(len(self.rows)))
        def delete(self,*_items):self.deleted+=1;self.rows=[]
        def insert(self,*_args,**kwargs):self.rows.append(kwargs["values"]);return str(len(self.rows)-1)
        def selection(self):return self.selected
        def selection_set(self,item):self.selected=(item,)
        def index(self,item):return int(item)
    state=ConnectionState(); state.set_brand("Simulator")
    app=SimpleNamespace(
        tags=[tag],tag_runtime=runtime,alarms=[],connection_state=state,
        dashboard_search_entry=SimpleNamespace(get=lambda:""),dashboard_filter_menu=SimpleNamespace(get=lambda:"All"),
        _dashboard_sort_column="name",_dashboard_sort_descending=False,_dashboard_selected_name=None,
        dashboard_tag_table=Table(),_dashboard_visible_tags=[],
        dashboard_count_label=SimpleNamespace(configure=lambda **_kwargs:None),
        dashboard_detail_labels={},
    )
    monkeypatch.setattr(dashboard_tab,"refresh_dashboard_detail",lambda _app:None)
    dashboard_tab.refresh_dashboard_table(app)
    dashboard_tab.refresh_dashboard_table(app)
    assert app.dashboard_tag_table.deleted == 1
