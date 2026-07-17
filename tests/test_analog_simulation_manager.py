from types import SimpleNamespace

import pytest

from core.tag_model import TagDefinition
from core.tag_runtime import RuntimeTagCache, RuntimeValueSource
from services.plc_service import PLCService
from ui import analog_tab, tag_manager
from ui.analog_profiles import AnalogSimulationManager, canonical_analog_profile


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def analog_tag(name, index=0, *, enabled=True, data_type="REAL"):
    return TagDefinition(
        name, data_type, "Input", f"A{index}", enabled,
        enabled_trend=True, enabled_dashboard=True,
    )


def manager_app(tags, *, internal_simulator=False, max_writes=100):
    clock = Clock()
    cache = RuntimeTagCache()
    cache.sync(tags)
    callbacks = {}
    cancelled = []
    next_job = [0]
    service = PLCService(runtime_cache=cache) if internal_simulator else None
    if service is not None:
        assert service.connect("Simulator", "")
    app = SimpleNamespace(
        tags=tags,
        tag_runtime=cache,
        analog_profile_running={},
        analog_simulations={},
        is_closing=False,
        _shutdown_started=False,
        _analog_selected_tag_name=None,
        values={},
    )

    def schedule_job(_delay, callback):
        next_job[0] += 1
        job = f"analog-{next_job[0]}"
        callbacks[job] = callback
        return job

    def cancel_job(job):
        callbacks.pop(job, None)
        cancelled.append(job)

    def write_analog_tag(tag, value, notify=False):
        assert notify is False
        if service is not None:
            result = service.write_numeric(tag, value)
            source = RuntimeValueSource.PLC
        else:
            result = int(value) if tag.data_type == "INT" else float(value)
            cache.update(tag.name, result, RuntimeValueSource.SIMULATION)
            source = RuntimeValueSource.SIMULATION
        app.values[tag.name] = (result, source)
        return result

    app.schedule_job = schedule_job
    app.cancel_job = cancel_job
    app.write_analog_tag = write_analog_tag
    manager = AnalogSimulationManager(
        app, clock=clock, max_writes_per_tick=max_writes
    )
    app.analog_simulation_manager = manager
    return app, manager, clock, callbacks, cancelled


def config(mode="Ramp", minimum=0, maximum=100, step=1, interval=100):
    return {
        "mode": mode,
        "min": minimum,
        "max": maximum,
        "step": step,
        "interval_ms": interval,
    }


def test_two_tags_run_simultaneously_and_starting_b_does_not_stop_a():
    tag_a, tag_b = analog_tag("A"), analog_tag("B", 1)
    app, manager, _, callbacks, _ = manager_app([tag_a, tag_b])
    state_a = manager.start(tag_a, config("Ramp", step=2))
    manager.start(tag_b, config("Step", maximum=20))

    assert state_a.running is True
    assert manager.active_count == 2
    assert len(callbacks) == 1
    assert manager.tick(now=0.0, reschedule=False) == 2
    assert app.tag_runtime.get_value("A") == 2
    assert app.tag_runtime.get_value("B") == 20
    assert state_a.running is True


def test_profiles_keep_independent_phase_interval_and_bounds(monkeypatch):
    tags = [analog_tag(name, i) for i, name in enumerate(("Ramp", "Step", "Random"))]
    app, manager, _, _, _ = manager_app(tags)
    ramp = manager.start(tags[0], config("Ramp", 0, 4, 2, 100))
    step = manager.start(tags[1], config("Step", 10, 20, 3, 500))
    random_state = manager.start(tags[2], config("Random", 30, 40, 7, 200))
    monkeypatch.setattr(
        random_state.random_generator, "randint", lambda low, high: 37
    )

    manager.tick(now=0.0, reschedule=False)
    manager.tick(now=0.11, reschedule=False)
    manager.tick(now=0.211, reschedule=False)

    assert ramp.phase == 3
    assert ramp.current_value == 2
    assert ramp.direction == -1
    assert step.phase == 1
    assert step.current_value == 20
    assert random_state.phase == 2
    assert random_state.current_value == 37
    assert app.tag_runtime.get_value("Ramp") == 2
    assert app.tag_runtime.get_value("Step") == 20


def test_manual_profile_is_independent_and_requires_no_scheduler():
    tag = analog_tag("Manual")
    _, manager, _, callbacks, _ = manager_app([tag])
    state = manager.start(tag, config("Manual"))
    assert state.running is True
    assert manager.callback_count == 0
    assert callbacks == {}


def test_start_all_only_starts_enabled_analog_inputs_and_stop_all_is_safe():
    enabled = [analog_tag(f"A{i}", i) for i in range(3)]
    disabled = analog_tag("Disabled", 10, enabled=False)
    output = TagDefinition("Output", "REAL", "Output", "A11", True)
    digital = TagDefinition("Digital", "BOOL", "Input", "D0", True)
    app, manager, _, callbacks, _ = manager_app(enabled + [disabled, output, digital])
    app.analog_controls = []
    app.analog_tags = []
    app.is_rebuilding = False
    app._analog_rebuilding = False
    app._analog_profile_cache = {
        tag.name: {"tag": tag.name, **config("Ramp", step=index + 1)}
        for index, tag in enumerate(enabled)
    }

    assert analog_tab.start_all_analog_simulations(app) == 3
    assert set(manager.states) == {"A0", "A1", "A2"}
    assert len(callbacks) == 1
    assert analog_tab.stop_all_analog_simulations(app) == 0
    assert not any(state.running for state in manager.states.values())
    assert callbacks == {}


def test_editor_selection_is_not_runtime_source_of_truth():
    tag_a, tag_b = analog_tag("A"), analog_tag("B", 1)
    app, manager, _, _, _ = manager_app([tag_a, tag_b])
    state_a = manager.start(tag_a, config("Ramp", step=5))
    manager.start(tag_b, config("Step", maximum=50))

    app.analog_tags = [tag_b]
    app._analog_selected_tag_name = tag_b.name
    manager.tick(now=0.0, reschedule=False)

    assert state_a.running is True
    assert state_a.phase == 1
    assert app.tag_runtime.get_value(tag_a.name) == 5


def test_runtime_cache_exposes_multiple_values_to_all_consumers():
    tags = [analog_tag(f"A{i}", i) for i in range(4)]
    app, manager, _, _, _ = manager_app(tags)
    for index, tag in enumerate(tags):
        manager.start(tag, config("Ramp", step=index + 1))
    manager.tick(now=0.0, reschedule=False)

    snapshot = app.tag_runtime.snapshot()
    assert {tag.tag_id: index + 1.0 for index, tag in enumerate(tags)} == {
        tag_id: item.value for tag_id, item in snapshot.items()
    }
    assert all(item.source == RuntimeValueSource.SIMULATION for item in snapshot.values())


def test_one_scheduler_callback_for_five_hundred_active_tags_and_clean_shutdown():
    tags = [analog_tag(f"A{i}", i) for i in range(500)]
    _, manager, _, callbacks, cancelled = manager_app(tags)
    manager.start_many((tag, config("Ramp", step=1, interval=500)) for tag in tags)

    assert manager.active_count == 500
    assert len(callbacks) == 1
    manager.shutdown()
    assert callbacks == {}
    assert len(cancelled) == 1
    assert manager.active_count == 0


@pytest.mark.parametrize("count", [10, 100, 500])
def test_internal_simulator_stress_updates_every_concurrent_tag(count):
    tags = [analog_tag(f"A{i}", i) for i in range(count)]
    app, manager, _, callbacks, _ = manager_app(
        tags, internal_simulator=True, max_writes=100
    )
    manager.start_many((tag, config("Ramp", interval=500)) for tag in tags)
    for _ in range((count + 99) // 100):
        manager.tick(now=0.0, reschedule=False)

    assert manager.active_count == count
    assert len(callbacks) == 1
    assert all(app.tag_runtime.get_value(tag.name) == 1.0 for tag in tags)
    assert manager.max_tick_duration_ms < 100


def test_reconcile_stops_removed_or_disabled_tags():
    tag = analog_tag("A")
    _, manager, _, _, _ = manager_app([tag])
    manager.start(tag, config("Ramp"))
    manager.reconcile([analog_tag("A", enabled=False)])
    assert manager.states["A"].running is False


class Status:
    def __init__(self):
        self.options = {}

    def configure(self, **options):
        self.options.update(options)


class EditorValue(Status):
    def __init__(self, value=""):
        super().__init__()
        self.value = str(value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = str(value)

    def delete(self, *_args):
        self.value = ""

    def insert(self, _index, value):
        self.value = str(value)


class AnalogTable:
    def __init__(self, rows):
        self.rows = [tuple(row) for row in rows]

    def get_children(self):
        return tuple(range(len(self.rows)))

    def item(self, item, option=None, **options):
        if "values" in options:
            self.rows[int(item)] = tuple(options["values"])
        if option == "values":
            return self.rows[int(item)]
        return {"values": self.rows[int(item)]}

    def winfo_exists(self):
        return True


def attach_editor(app, selected_tag, visible_tags=None):
    visible_tags = visible_tags or [selected_tag]
    app._analog_table_tags = visible_tags
    app.analog_table = AnalogTable([
        (tag.address, tag.name, tag.data_type, 0, "Manual", "ready")
        for tag in visible_tags
    ])
    app._analog_selected_tag_name = selected_tag.name
    app.analog_tags = [selected_tag]
    app.analog_editor = {
        "interactive": True,
        "profile_mode": EditorValue("Manual"),
        "min_entry": EditorValue("0"),
        "max_entry": EditorValue("27648"),
        "step_entry": EditorValue("500"),
        "interval_entry": EditorValue("500"),
        "profile_status": EditorValue(),
        "live": EditorValue(),
    }
    app.analog_controls = [app.analog_editor]
    app._analog_structure_initialized = True
    app._analog_rebuilding = False
    app.is_rebuilding = False
    return app.analog_editor


def test_editor_mode_change_immediately_updates_canonical_config_and_treeview():
    tag = analog_tag("A")
    app, _, _, _, _ = manager_app([tag])
    editor = attach_editor(app, tag)
    dirty = []
    app.mark_project_modified = lambda: dirty.append(True)

    editor["profile_mode"].set("Ramp")
    analog_tab.on_analog_profile_editor_changed(app, "Ramp")

    assert app._analog_profile_cache[tag.tag_id]["mode"] == "Ramp"
    assert app.analog_table.rows[0][4] == "Ramp"
    assert editor["profile_status"].options["text"] == "Ramp READY"
    assert dirty == [True]


def test_start_selected_uses_canonical_displayed_mode_and_refreshes_row():
    tag = analog_tag("A")
    app, manager, _, callbacks, _ = manager_app([tag])
    editor = attach_editor(app, tag)
    app.mark_project_modified = lambda: None
    editor["profile_mode"].set("Ramp")
    analog_tab.on_analog_profile_editor_changed(app, "Ramp")

    analog_tab.on_profile_start(app, 0)

    assert manager.states[tag.name].mode == "Ramp"
    assert manager.states[tag.name].running is True
    assert app._analog_profile_cache[tag.tag_id]["mode"] == "Ramp"
    assert app.analog_table.rows[0][4] == "Ramp"
    assert app.analog_table.rows[0][5].startswith("Running")
    assert len(callbacks) == 1


def test_runtime_state_is_separate_from_canonical_configuration():
    tag = analog_tag("A")
    app, manager, _, _, _ = manager_app([tag])
    manager.start(tag, config("Ramp", 0, 10, 5, 100))
    manager.tick(now=0.0, reschedule=False)

    profile = app._analog_profile_cache[tag.tag_id]
    state = manager.states[tag.name]
    assert profile["mode"] == "Ramp"
    assert "phase" not in profile and "direction" not in profile
    assert state.phase == 1 and state.current_value == 5

    profile["mode"] = "Random"
    assert state.mode == "Ramp"
    manager.start(tag, schedule=False)
    assert manager.states[tag.name].mode == "Random"


def test_select_all_refreshes_all_rows_from_canonical_modes(monkeypatch):
    tags = [analog_tag(name, index, enabled=False) for index, name in enumerate(
        ("ManualA", "ManualB", "Random", "Step")
    )]
    app, _, _, callbacks, _ = manager_app(tags)
    editor = attach_editor(app, tags[0], tags)
    app._analog_profile_cache = {
        "Random": {"tag": "Random", **config("Random")},
        "Step": {"tag": "Step", **config("Step")},
    }
    dirty = []
    app.mark_project_modified = lambda: dirty.append(True)
    app.status_label = Status()
    monkeypatch.setattr(tag_manager, "refresh_tag_table", lambda _app: None)
    monkeypatch.setattr(
        analog_tab, "refresh_analog_tab",
        lambda target: [
            analog_tab.refresh_analog_tree_row(target, tag.name) for tag in tags
        ],
    )

    tag_manager.set_all_tag_option(app, "enabled_sim", True)

    assert [app._analog_profile_cache[tag.tag_id]["mode"] for tag in tags] == [
        "Ramp", "Ramp", "Random", "Step",
    ]
    assert [row[4] for row in app.analog_table.rows] == [
        "Ramp", "Ramp", "Random", "Step",
    ]
    assert editor["profile_mode"].get() == "Ramp"
    assert dirty == [True]
    assert callbacks == {}


def test_start_all_uses_all_canonical_modes_not_selected_tag():
    tags = [analog_tag(f"A{index}", index) for index in range(20)]
    app, manager, _, callbacks, _ = manager_app(tags)
    app.analog_controls = []
    app.analog_tags = []
    app.is_rebuilding = False
    app._analog_rebuilding = False
    app.mark_project_modified = lambda: None
    app._analog_profile_cache = {
        tags[1].name: {"tag": tags[1].name, **config("Random")},
        tags[2].name: {"tag": tags[2].name, **config("Step")},
    }

    assert analog_tab.start_all_analog_simulations(app) == 20
    assert manager.active_count == 20
    assert manager.states[tags[0].name].mode == "Ramp"
    assert manager.states[tags[1].name].mode == "Random"
    assert manager.states[tags[2].name].mode == "Step"
    assert all(state.mode != "Manual" for state in manager.states.values())
    assert len(callbacks) == 1


def test_project_restore_updates_editor_and_profile_tree_column():
    tag = analog_tag("A")
    app, _, _, _, _ = manager_app([tag])
    editor = attach_editor(app, tag)

    from ui import project_config
    project_config._restore_analog_profiles(app, [{
        "tag": "A", "mode": "Ramp", "min": "10", "max": "90",
        "step": "5", "interval_ms": "250", "enabled_sim": True,
    }])

    assert app._analog_profile_cache[tag.tag_id]["mode"] == "Ramp"
    assert editor["profile_mode"].get() == "Ramp"
    assert app.analog_table.rows[0][4] == "Ramp"


def test_select_all_converts_only_manual_profiles_to_ramp(monkeypatch):
    tags = [analog_tag(mode, index, enabled=False) for index, mode in enumerate(
        ("Manual", "Ramp", "Random", "Step")
    )]
    app, _, _, callbacks, _ = manager_app(tags)
    app._analog_profile_cache = {
        tag.name: {
            "tag": tag.name, "mode": tag.name, "min": "10", "max": "90",
            "step": "5", "interval_ms": "250",
        }
        for tag in tags
    }
    dirty = []
    app.mark_project_modified = lambda: dirty.append(True)
    app.status_label = Status()
    monkeypatch.setattr(tag_manager, "refresh_tag_table", lambda _app: None)

    tag_manager.set_all_tag_option(app, "enabled_sim", True)

    assert all(tag.enabled_sim for tag in tags)
    manual = app._analog_profile_cache[tags[0].tag_id]
    assert manual["mode"] == "Ramp"
    assert manual["min"] == "10"
    assert manual["max"] == "90"
    assert manual["step"] == "5"
    assert manual["interval_ms"] == "250"
    assert manual["enabled_sim"] is True
    assert [app._analog_profile_cache[tag.tag_id]["mode"] for tag in tags[1:]] == [
        "Ramp", "Random", "Step"
    ]
    assert dirty == [True]
    assert callbacks == {}
    assert app.status_label.options["text"] == (
        "All analog simulations enabled; Manual tags set to Ramp"
    )


def test_select_all_defaults_missing_profiles_to_ramp_then_start_all_changes_values(
    monkeypatch,
):
    tags = [analog_tag(f"A{index}", index, enabled=False) for index in range(3)]
    app, manager, _, callbacks, _ = manager_app(tags)
    app.analog_controls = []
    app.analog_tags = []
    app.is_rebuilding = False
    app._analog_rebuilding = False
    app.mark_project_modified = lambda: None
    app.status_label = Status()
    monkeypatch.setattr(tag_manager, "refresh_tag_table", lambda _app: None)

    tag_manager.set_all_tag_option(app, "enabled_sim", True)
    assert all(
        app._analog_profile_cache[tag.tag_id]["mode"] == "Ramp" for tag in tags
    )
    assert callbacks == {}

    assert analog_tab.start_all_analog_simulations(app) == 3
    assert len(callbacks) == 1
    manager.tick(now=0.0, reschedule=False)
    assert all(app.tag_runtime.get_value(tag.name) == 500.0 for tag in tags)


def test_deselect_all_preserves_modes_and_parameters_and_stops_profiles(monkeypatch):
    tags = [analog_tag("Ramp"), analog_tag("Random", 1)]
    app, manager, _, callbacks, _ = manager_app(tags)
    app._analog_profile_cache = {
        "Ramp": {"tag": "Ramp", **config("Ramp", 1, 9, 2, 250)},
        "Random": {"tag": "Random", **config("Random", 3, 30, 4, 500)},
    }
    for tag in tags:
        canonical_analog_profile(app, tag)
    original_modes = {
        name: profile["mode"] for name, profile in app._analog_profile_cache.items()
    }
    dirty = []
    app.mark_project_modified = lambda: dirty.append(True)
    monkeypatch.setattr(tag_manager, "refresh_tag_table", lambda _app: None)
    manager.start_many(
        (tag, canonical_analog_profile(app, tag)) for tag in tags
    )
    assert len(callbacks) == 1

    tag_manager.set_all_tag_option(app, "enabled_sim", False)

    assert not any(tag.enabled_sim for tag in tags)
    assert {
        name: profile["mode"] for name, profile in app._analog_profile_cache.items()
    } == original_modes
    assert all(
        profile["enabled_sim"] is False
        for profile in app._analog_profile_cache.values()
    )
    assert manager.active_count == 0
    assert callbacks == {}
    assert dirty == [True]
