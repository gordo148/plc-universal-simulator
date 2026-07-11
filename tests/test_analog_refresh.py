from types import SimpleNamespace

import pytest

from core.tag_model import TagDefinition
from core.tag_runtime import RuntimeTagCache
from ui import analog_tab, main_window


class FakeWidget:
    def __init__(self, *_args, command=None, **_kwargs):
        self.command = command
        self.value = "Manual"

    def pack(self, **_kwargs):
        return self

    def grid(self, **_kwargs):
        return self

    def insert(self, _index, value):
        self.value = value

    def set(self, value):
        self.value = value

    def get(self):
        return self.value

    def configure(self, **kwargs):
        if "text" in kwargs:
            self.value = kwargs["text"]

    def destroy(self):
        pass


class FakeScroll:
    def __init__(self):
        self.children = []

    def winfo_children(self):
        return list(self.children)


@pytest.fixture
def fake_ctk(monkeypatch):
    for name in (
        "CTkFrame", "CTkLabel", "CTkEntry", "CTkSlider",
        "CTkOptionMenu", "CTkButton",
    ):
        monkeypatch.setattr(analog_tab.ctk, name, FakeWidget)


@pytest.mark.parametrize("count", [73, 500])
def test_analog_refresh_builds_large_real_tag_sets_without_writes(fake_ctk, count):
    tags = [
        TagDefinition(f"Real{i}", "REAL", "Input", f"DBD{i * 4}", enabled_sim=True)
        for i in range(count)
    ]
    app = SimpleNamespace(
        analog_scroll=FakeScroll(),
        analog_controls=[],
        analog_tags=[],
        analog_profile_running={},
        analog_profile_directions={},
        tag_runtime=RuntimeTagCache(),
        is_rebuilding=True,
        update_analog=lambda *_args: (_ for _ in ()).throw(
            AssertionError("widget construction must not write values")
        ),
    )

    analog_tab.begin_analog_refresh(app, tags)
    for index, tag in enumerate(tags):
        analog_tab.create_analog_row(app, index, tag)
    analog_tab.finish_analog_refresh(app)

    assert len(app.analog_controls) == count
    assert app.analog_tags == tags
    assert all(control["slider"].value == 0 for control in app.analog_controls)


def test_plc_only_analog_tags_create_read_only_rows(fake_ctk):
    tags = [
        TagDefinition(f"PLCReal{i}", "REAL", "Input", f"DBD{i * 4}", enabled_sim=False)
        for i in range(500)
    ]
    app = SimpleNamespace(
        analog_scroll=FakeScroll(),
        analog_controls=[],
        analog_tags=[],
        analog_profile_running={},
        analog_profile_directions={},
        tag_runtime=RuntimeTagCache(),
        is_rebuilding=True,
    )

    analog_tab.begin_analog_refresh(app, tags)
    for index, tag in enumerate(tags):
        analog_tab.create_analog_row(app, index, tag)
    analog_tab.finish_analog_refresh(app)

    assert len(app.analog_controls) == 500
    assert all(control["interactive"] is False for control in app.analog_controls)
    # Heavy controls remain allocated in the reusable pool but are hidden for
    # PLC-only tags, allowing the row to be rebound without reconstruction.
    assert all("slider" in control for control in app.analog_controls)
    assert all("profile_mode" in control for control in app.analog_controls)


def test_read_only_analog_row_accepts_runtime_updates(fake_ctk):
    tag = TagDefinition("Temperature", "REAL", "Input", "DBD0", enabled_sim=False)
    app = SimpleNamespace(
        analog_scroll=FakeScroll(),
        analog_controls=[],
        analog_tags=[],
        analog_profile_running={},
        analog_profile_directions={},
        tag_runtime=RuntimeTagCache(),
        is_rebuilding=False,
    )
    analog_tab.create_analog_row(app, 0, tag)

    main_window.PLCSimulator.update_analog_ui(app, 0, 42.5)

    assert app.analog_controls[0]["live"].value == "42.5"


def test_slider_callback_during_rebuild_is_ignored():
    calls = []
    app = SimpleNamespace(
        is_rebuilding=True,
        update_analog=lambda *args: calls.append(args),
    )

    analog_tab.on_slider_changed(app, 4, 123.0)

    assert calls == []


@pytest.mark.parametrize("count", [73, 500])
def test_import_does_not_rebuild_analog_tags(monkeypatch, count):
    tags = [
        TagDefinition(f"Real{i}", "REAL", "Input", f"DBD{i * 4}")
        for i in range(count)
    ]
    queue = []
    created = []
    completed = []
    errors = []

    class Root:
        def after(self, _delay, callback):
            job = len(queue) + 1
            queue.append((job, callback))
            return job

        def after_cancel(self, _job):
            pass

    app = SimpleNamespace(
        tags=tags,
        app=Root(),
        _closing=False,
        _rebuild_after_jobs=set(),
        tag_runtime=RuntimeTagCache(),
        clear_signal_frames=lambda: None,
        analog_scroll=FakeScroll(),
        analog_controls=[],
        analog_tags=[],
        analog_profile_running={},
        analog_profile_directions={},
        _tag_manager_initialized=False,
        _feedback_initialized=False,
        _pid_initialized=False,
        _alarm_initialized=False,
        _trend_initialized=False,
        _dirty_tabs=set(),
        is_closing=False,
        _pending_jobs=set(),
    )
    app.schedule_job = lambda delay, callback: main_window.PLCSimulator.schedule_job(app, delay, callback)
    app.cancel_job = lambda job: main_window.PLCSimulator.cancel_job(app, job)
    app._cancel_rebuild_jobs = lambda: main_window.PLCSimulator._cancel_rebuild_jobs(app)
    monkeypatch.setattr(main_window, "get_input_bool_tags", lambda _app: [])
    monkeypatch.setattr(main_window, "get_input_analog_tags", lambda _app: tags)
    monkeypatch.setattr(main_window, "get_invalid_tags_for_brand", lambda _app: [])
    monkeypatch.setattr(main_window, "create_analog_row", lambda _app, index, tag: created.append((index, tag)))
    monkeypatch.setattr(main_window, "begin_analog_refresh", lambda _app, received: None)
    monkeypatch.setattr(main_window, "finish_analog_refresh", lambda _app: None)
    monkeypatch.setattr(main_window, "update_tag_address_context", lambda _app: None)
    monkeypatch.setattr(main_window, "update_dashboard", lambda *_args: None)

    main_window.PLCSimulator.refresh_after_import(
        app,
        lambda: completed.append(True),
        lambda error: errors.append(error),
    )
    callbacks_run = 0
    while queue:
        _job, callback = queue.pop(0)
        callback()
        callbacks_run += 1

    assert created == []
    assert callbacks_run == 1
    assert app._dirty_tabs == set()
    assert completed == [True]
    assert errors == []


def test_lazy_analog_load_pages_and_batches_five_hundred_tags(monkeypatch):
    from ui import tag_manager

    tags = [
        TagDefinition(f"Real{i}", "REAL", "Input", f"DBD{i * 4}")
        for i in range(500)
    ]
    queue = []
    created = []

    class Root:
        def after(self, _delay, callback):
            job = len(queue) + 1
            queue.append((job, callback))
            return job

        def after_cancel(self, _job):
            pass

    app = SimpleNamespace(
        app=Root(),
        _closing=False,
        _dirty_tabs={"Entradas Analógicas"},
        _analog_after_jobs=set(),
        _analog_rebuilding=False,
        is_closing=False,
        _pending_jobs=set(),
        analog_page=0,
        analog_search_entry=FakeWidget(),
        analog_loading_label=FakeWidget(),
        analog_previous_button=FakeWidget(),
        analog_next_button=FakeWidget(),
        analog_scroll=FakeScroll(),
        analog_controls=[],
        analog_tags=[],
        analog_profile_running={},
        analog_profile_directions={},
    )
    app.schedule_job = lambda delay, callback: main_window.PLCSimulator.schedule_job(app, delay, callback)
    app.cancel_job = lambda job: main_window.PLCSimulator.cancel_job(app, job)
    app.analog_search_entry.value = ""
    monkeypatch.setattr(tag_manager, "get_input_analog_tags", lambda _app: tags)
    class RowFrame:
        def pack(self, **_kwargs): pass
        def pack_forget(self): pass

    monkeypatch.setattr(
        analog_tab, "create_analog_row_widgets",
        lambda _app: {"frame": RowFrame(), "current_tag_index": None, "tag": None},
    )
    monkeypatch.setattr(
        analog_tab, "bind_analog_row",
        lambda _app, row, index, tag: created.append((index, tag)),
    )

    analog_tab.refresh_analog_tab(app)
    batches = 0
    while queue:
        _job, callback = queue.pop(0)
        callback()
        batches += 1

    assert len(created) == 50
    assert batches == 5
    assert app._analog_rebuilding is False
    assert "Entradas Analógicas" not in app._dirty_tabs


def test_pending_analog_jobs_cancel_safely_on_close():
    cancelled = []
    app = SimpleNamespace(
        app=SimpleNamespace(after_cancel=lambda job: cancelled.append(job)),
        _analog_after_jobs={"job-1", "job-2"},
        _analog_rebuilding=True,
        _closing=True,
        is_closing=True,
        _pending_jobs={"job-1", "job-2"},
    )
    app.cancel_job = lambda job: main_window.PLCSimulator.cancel_job(app, job)

    analog_tab.cancel_analog_refresh(app)

    assert set(cancelled) == {"job-1", "job-2"}
    assert app._analog_after_jobs == set()
    assert app._analog_rebuilding is False
