from types import SimpleNamespace

from ui import analog_profiles, main_window


class FakeRoot:
    def __init__(self):
        self.callbacks = {}
        self.cancelled = []
        self.destroyed = False
        self.next_id = 0

    def after(self, _delay, callback):
        self.next_id += 1
        job = f"after-{self.next_id}"
        self.callbacks[job] = callback
        return job

    def after_cancel(self, job):
        self.cancelled.append(job)
        self.callbacks.pop(job, None)

    def destroy(self):
        self.destroyed = True


def scheduler_app():
    root = FakeRoot()
    app = SimpleNamespace(
        app=root,
        is_closing=False,
        _pending_jobs=set(),
    )
    app.schedule_job = lambda delay, callback: main_window.PLCSimulator.schedule_job(app, delay, callback)
    app.cancel_job = lambda job: main_window.PLCSimulator.cancel_job(app, job)
    app.cancel_pending_jobs = lambda: main_window.PLCSimulator.cancel_pending_jobs(app)
    return app


def test_all_after_callbacks_are_tracked_and_cancelled():
    app = scheduler_app()
    app.schedule_job(1, lambda: None)
    app.schedule_job(500, lambda: None)
    jobs = set(app._pending_jobs)

    app.is_closing = True
    app.cancel_pending_jobs()

    assert set(app.app.cancelled) == jobs
    assert app._pending_jobs == set()


def test_delayed_callback_is_noop_after_shutdown_starts():
    app = scheduler_app()
    calls = []
    job = app.schedule_job(1, lambda: calls.append(True))

    app.is_closing = True
    app.app.callbacks[job]()

    assert calls == []


def test_close_immediately_after_import_cancels_jobs_before_destroy():
    app = scheduler_app()
    app.schedule_job(1, lambda: None)  # import/Tag Manager continuation
    disconnected = []
    saved = []
    app.has_unsaved_changes = lambda: False
    app.cyclic_read_enabled = True
    app.pid_running = True
    app.trend_running = True
    app.analog_profile_running = {0: True}
    app.cancel_pending_tab_refreshes = lambda: None
    app.is_rebuilding = True
    app.plc_service = SimpleNamespace(disconnect=lambda: disconnected.append(True))
    app._save_settings = lambda: saved.append(True)

    main_window.PLCSimulator.on_close(app)

    assert app.is_closing is True
    assert app.cyclic_read_enabled is False
    assert app.pid_running is False
    assert app.analog_profile_running == {0: False}
    assert app._pending_jobs == set()
    assert disconnected == [True]
    assert saved == [True]
    assert app.app.destroyed is True


def test_close_disconnects_scroll_callbacks_before_root_destroy():
    events = []
    app = scheduler_app()
    app.has_unsaved_changes = lambda: False
    app.cyclic_read_enabled = False
    app.pid_running = False
    app.analog_profile_running = {}
    app.cancel_pending_tab_refreshes = lambda: events.append("cancel-tabs")
    app.plc_service = SimpleNamespace(disconnect=lambda: events.append("disconnect-plc"))
    app._save_settings = lambda: events.append("save")
    app.digital_scroll = SimpleNamespace(
        disconnect_scroll_callbacks=lambda: events.append("disconnect-digital")
    )
    app.analog_scroll = SimpleNamespace(
        disconnect_scroll_callbacks=lambda: events.append("disconnect-analog")
    )
    app.app.destroy = lambda: events.append("destroy-root")

    main_window.PLCSimulator.on_close(app)

    assert events.index("disconnect-digital") < events.index("destroy-root")
    assert events.index("disconnect-analog") < events.index("destroy-root")


def test_close_during_plc_polling_does_not_reschedule():
    app = scheduler_app()
    app.is_closing = True
    app.cyclic_read_enabled = True

    main_window.PLCSimulator.start_cyclic_read(app)

    assert app._pending_jobs == set()


def test_close_while_simulation_profile_running_is_safe():
    calls = []
    app = SimpleNamespace(
        is_closing=True,
        analog_profile_running={0: True},
        write_analog_by_index=lambda *_args: calls.append(True),
    )

    analog_profiles.run_profile(app, 0)

    assert calls == []


def test_on_close_executes_only_once():
    app = scheduler_app()
    app.has_unsaved_changes = lambda: False
    app.cyclic_read_enabled = False
    app.pid_running = False
    app.analog_profile_running = {}
    app.cancel_pending_tab_refreshes = lambda: None
    app.plc_service = SimpleNamespace(disconnect=lambda: None)
    saves, destroys = [], []
    app._save_settings = lambda: saves.append(True)
    app.app.destroy = lambda: destroys.append(True)

    main_window.PLCSimulator.on_close(app)
    main_window.PLCSimulator.on_close(app)

    assert saves == [True]
    assert destroys == [True]


def test_clean_close_does_not_auto_save_project():
    app = scheduler_app()
    app.has_unsaved_changes = lambda: False
    app.save_project = lambda: (_ for _ in ()).throw(AssertionError("project auto-save"))
    app.cyclic_read_enabled = False
    app.pid_running = False
    app.analog_profile_running = {}
    app.cancel_pending_tab_refreshes = lambda: None
    app.plc_service = SimpleNamespace(disconnect=lambda: None)
    app._save_settings = lambda: None
    main_window.PLCSimulator.on_close(app)
    assert app.app.destroyed is True


def test_worker_join_is_bounded_and_not_repeated():
    joins = []
    worker = SimpleNamespace(
        name="test-worker", join=lambda timeout: joins.append(timeout),
        is_alive=lambda: False,
    )
    event = SimpleNamespace(set=lambda: None)
    app = SimpleNamespace(worker_thread=worker, polling_thread=worker, worker_stop_event=event)
    main_window.PLCSimulator._stop_shutdown_workers(app)
    assert len(joins) == 1
    assert 0 <= joins[0] <= 0.25
