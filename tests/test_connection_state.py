from types import SimpleNamespace

from ui import dashboard_tab, main_window, project_config


class Var:
    def __init__(self, value): self.value = value
    def get(self): return self.value
    def set(self, value): self.value = str(value)


class DestroyedEntry:
    def get(self): raise RuntimeError("destroyed widget was accessed")


class Value:
    def __init__(self, value): self.value = value
    def get(self): return self.value


def connection_vars():
    return {"ip":Var("192.168.0.84"), "rack":Var("0"), "slot":Var("1"), "db_number":Var("2000"), "port":Var("502"), "slave_id":Var("1"), "coil_start":Var("0"), "register_start":Var("0"), "omron_port":Var("9600"), "destination_node":Var("0"), "source_node":Var("1")}


def stale_entries(app):
    app.ip_entry = app.rack_entry = app.slot_entry = app.db_entry = DestroyedEntry()
    return app


def test_dashboard_connection_summary_uses_persistent_state():
    app = stale_entries(SimpleNamespace(connection_vars=connection_vars()))
    assert dashboard_tab._connection_summary(app, "Siemens") == "192.168.0.84 · Rack 0 Slot 1 DB 2000"


def test_connect_uses_persistent_siemens_values(monkeypatch):
    calls = []
    service = SimpleNamespace(connect=lambda *args, **kwargs: calls.append((args, kwargs)) or True)
    app = stale_entries(SimpleNamespace(connection_vars=connection_vars(), _connection_ui_rebuilding=False, brand_menu=Value("Siemens"), plc_service=service, status_label=SimpleNamespace(configure=lambda **_kw: None), cyclic_read_enabled=False, start_cyclic_read=lambda: None))
    main_window.PLCSimulator.connect(app)
    assert calls == [(('Siemens', '192.168.0.84'), {'rack':'0', 'slot':'1', 'db_number':'2000'})]


def test_project_snapshot_uses_persistent_state(project_app):
    project_app.connection_vars = connection_vars()
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
    app = stale_entries(SimpleNamespace(connection_vars=connection_vars(), app=None))
    project_config._restore_connection_settings(app, "Siemens", {"rack":"2", "slot":"3", "db_number":"400"})
    assert [app.connection_vars[key].get() for key in ("rack","slot","db_number")] == ["2","3","400"]
