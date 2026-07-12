from types import SimpleNamespace
import inspect
import threading
import time

from core.connection_state import ConnectionState
from ui import dashboard_tab, header, main_window, project_config


class Var:
    def __init__(self, value): self.value = value
    def get(self): return self.value
    def set(self, value): self.value = str(value)


class DestroyedEntry:
    def get(self): raise RuntimeError("destroyed widget was accessed")


class Value:
    def __init__(self, value): self.value = value
    def get(self): return self.value


def connection_state():
    return ConnectionState(ip="192.168.0.84", rack="0", slot="1", db_number="2000")


def stale_entries(app):
    app.ip_entry = app.rack_entry = app.slot_entry = app.db_entry = DestroyedEntry()
    return app


def test_dashboard_connection_summary_uses_persistent_state():
    app = stale_entries(SimpleNamespace(connection_state=connection_state()))
    assert dashboard_tab._connection_summary(app, "Siemens") == "192.168.0.84 · Rack 0 Slot 1 DB 2000"


def test_connect_uses_persistent_siemens_values(monkeypatch):
    calls = []
    service = SimpleNamespace(connect=lambda *args, **kwargs: calls.append((args, kwargs)) or True)
    app = stale_entries(SimpleNamespace(connection_state=connection_state(), _connection_ui_rebuilding=False, plc_service=service, status_label=SimpleNamespace(configure=lambda **_kw: None), cyclic_read_enabled=False, start_cyclic_read=lambda: None, schedule_job=lambda *_args: None))
    main_window.PLCSimulator.connect(app)
    app.connection_thread.join(timeout=1)
    assert calls == [(('Siemens', '192.168.0.84'), {'rack':'0', 'slot':'1', 'db_number':'2000'})]


def test_blocking_driver_connect_does_not_block_tk_caller():
    release = threading.Event()
    service = SimpleNamespace(connect=lambda *_a, **_k: release.wait(5))
    app = SimpleNamespace(connection_state=connection_state(), _connection_ui_rebuilding=False, plc_service=service, status_label=SimpleNamespace(configure=lambda **_kw: None), schedule_job=lambda *_args: None)
    started = time.perf_counter()
    main_window.PLCSimulator.connect(app)
    elapsed = time.perf_counter() - started
    assert elapsed < 0.1
    assert app.connection_thread.daemon is True
    release.set(); app.connection_thread.join(timeout=1)


def test_project_snapshot_uses_persistent_state(project_app):
    project_app.connection_state = connection_state()
    stale_entries(project_app)
    connection = project_config.build_project_data(project_app)["plc"]
    assert connection["ip"] == "192.168.0.84"
    assert connection["settings"] == {"rack":"0", "slot":"1", "db_number":"2000"}


def test_update_brand_rebuilds_only_selected_options(monkeypatch):
    calls = []
    app = SimpleNamespace(_connection_ui_rebuilding=False, disconnect=lambda: calls.append("disconnect"), create_siemens_options=lambda: calls.append("siemens"), create_schneider_options=lambda: calls.append("schneider"), create_modbus_options=lambda: calls.append("modbus"), create_rockwell_options=lambda: calls.append("rockwell"), create_omron_options=lambda: calls.append("omron"), create_simulator_options=lambda: calls.append("simulator"), is_rebuilding=True)
    monkeypatch.setattr(main_window, "update_tag_address_context", lambda _app: None)
    for brand in ("Simulator", "Siemens", "Schneider", "Siemens", "Simulator"):
        main_window.PLCSimulator.update_brand(app, brand)
    assert calls == ["disconnect","simulator","disconnect","siemens","disconnect","schneider","disconnect","siemens","disconnect","simulator"]
    assert app._connection_ui_rebuilding is False


def test_connect_is_ignored_during_connection_rebuild():
    app = SimpleNamespace(_connection_ui_rebuilding=True, ip_entry=DestroyedEntry())
    assert main_window.PLCSimulator.connect(app) is None


def test_connection_restore_updates_model_without_entries():
    app = stale_entries(SimpleNamespace(connection_state=connection_state(), app=None))
    project_config._restore_connection_settings(app, "Siemens", {"rack":"2", "slot":"3", "db_number":"400"})
    assert [app.connection_state.get(key) for key in ("rack","slot","db_number")] == ["2","3","400"]


def test_connection_panel_switching_never_destroys_entries():
    source = inspect.getsource(header.clear_brand_frame)
    assert "grid_remove" in source
    assert ".destroy(" not in source


def test_persistent_value_change_does_not_touch_previous_entry():
    app = stale_entries(SimpleNamespace(connection_state=connection_state(), app=None))
    header.set_connection_value(app, "db_number", "3000")
    assert app.connection_state.db_number == "3000"
