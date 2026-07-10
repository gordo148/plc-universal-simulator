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
