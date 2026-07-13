"""Concurrent analog simulation runtime with one shared Tk scheduler."""

from dataclasses import dataclass, field
import logging
import math
import random
import time


LOGGER = logging.getLogger(__name__)
SUPPORTED_MODES = ("Manual", "Ramp", "Random", "Step")
DEFAULT_TICK_MS = 50
MIN_INTERVAL_MS = 100
DEFAULT_MAX_WRITES_PER_TICK = 100
DEFAULT_ANALOG_PROFILE = {
    "mode": "Manual",
    "min": "0",
    "max": "27648",
    "step": "500",
    "interval_ms": "500",
}


def normalize_analog_profile(raw_profile, tag, logger=None):
    """Return a safe canonical profile for persisted or editor-provided data.

    Project version 1 did not require analog profile records, so this accepts
    missing, partial, and older-key dictionaries without making project loading
    depend on a migration.
    """
    logger = logger or LOGGER
    issues = []
    if raw_profile is None:
        raw_profile = {}
    elif not isinstance(raw_profile, dict):
        issues.append(f"profile is {type(raw_profile).__name__}, expected object")
        raw_profile = {}

    def value_for(field, *aliases):
        for key in (field, *aliases):
            if key in raw_profile and raw_profile[key] is not None:
                return raw_profile[key]
        return DEFAULT_ANALOG_PROFILE[field]

    raw_mode = value_for("mode", "profile", "profile_mode")
    mode_by_name = {mode.casefold(): mode for mode in SUPPORTED_MODES}
    mode = mode_by_name.get(str(raw_mode).strip().casefold())
    if mode is None:
        issues.append(f"invalid mode {raw_mode!r}")
        mode = DEFAULT_ANALOG_PROFILE["mode"]

    def numeric_text(field, *aliases, positive=False, interval=False):
        raw_value = value_for(field, *aliases)
        try:
            if isinstance(raw_value, bool):
                raise ValueError
            number = float(str(raw_value).strip())
            if not math.isfinite(number) or (positive and number <= 0):
                raise ValueError
        except (TypeError, ValueError):
            issues.append(f"invalid {field} {raw_value!r}")
            return DEFAULT_ANALOG_PROFILE[field]
        if interval and number < MIN_INTERVAL_MS:
            issues.append(f"{field} {raw_value!r} clamped to {MIN_INTERVAL_MS}")
            return str(MIN_INTERVAL_MS)
        if interval:
            return str(int(number))
        if isinstance(raw_value, str):
            return raw_value.strip()
        return str(raw_value)

    minimum = numeric_text("min", "minimum", "min_value")
    maximum = numeric_text("max", "maximum", "max_value")
    if float(minimum) > float(maximum):
        issues.append(f"minimum {minimum!r} exceeds maximum {maximum!r}")
        minimum = DEFAULT_ANALOG_PROFILE["min"]
        maximum = DEFAULT_ANALOG_PROFILE["max"]
    step = numeric_text("step", "step_value", positive=True)
    interval_ms = numeric_text(
        "interval_ms", "interval", "profile_interval_ms",
        positive=True, interval=True,
    )

    enabled = getattr(tag, "enabled_sim", None)
    if enabled is None:
        raw_enabled = raw_profile.get("enabled_sim", False)
        if isinstance(raw_enabled, str):
            enabled = raw_enabled.strip().casefold() in ("1", "true", "yes", "on")
        else:
            enabled = bool(raw_enabled)

    profile = {
        "tag": tag.name,
        "mode": mode,
        "min": minimum,
        "max": maximum,
        "step": step,
        "interval_ms": interval_ms,
        "enabled_sim": bool(enabled),
    }
    if issues:
        logger.warning(
            "Analog profile normalized: tag=%s issues=%s",
            tag.name,
            "; ".join(issues),
        )
    return profile


def canonical_analog_profile(app, tag):
    """Return the normalized persistent profile dictionary for one tag."""
    cache = getattr(app, "_analog_profile_cache", None)
    if cache is None:
        cache = {}
        app._analog_profile_cache = cache
    profile = normalize_analog_profile(cache.get(tag.name), tag)
    cache[tag.name] = profile
    return profile


def update_canonical_analog_profile(app, tag, values):
    """Replace one canonical profile while keeping its stable tag identity."""
    current = canonical_analog_profile(app, tag)
    updated = dict(current)
    for field in ("mode", "min", "max", "step", "interval_ms"):
        if field in values:
            updated[field] = values[field]
    updated = normalize_analog_profile(updated, tag)
    app._analog_profile_cache[tag.name] = updated
    return updated, updated != current


def ensure_dynamic_analog_profiles(app, tags):
    """Convert canonical Manual profiles to Ramp without changing parameters."""
    changed = []
    for tag in tags:
        profile = canonical_analog_profile(app, tag)
        if profile["mode"] == "Manual":
            profile = dict(profile)
            profile["mode"] = "Ramp"
            app._analog_profile_cache[tag.name] = profile
            changed.append(tag.name)
    return changed


@dataclass
class AnalogSimulationState:
    """Volatile execution state for one analog tag."""

    tag: object
    running: bool
    mode: str
    current_value: float
    minimum: float
    maximum: float
    step: float
    interval_ms: int
    direction: int = 1
    phase: int = 0
    elapsed_ms: float = 0.0
    next_update_time: float = 0.0
    started_at: float = 0.0
    last_update_time: float | None = None
    csv_position: int = 0
    random_generator: random.Random = field(default_factory=random.Random, repr=False)


class AnalogSimulationManager:
    """Run independent per-tag profiles from one bounded scheduler callback."""

    def __init__(
        self,
        app,
        *,
        tick_ms=DEFAULT_TICK_MS,
        max_writes_per_tick=DEFAULT_MAX_WRITES_PER_TICK,
        clock=time.monotonic,
    ):
        self.app = app
        self.tick_ms = max(20, int(tick_ms))
        self.max_writes_per_tick = max(1, int(max_writes_per_tick))
        self.clock = clock
        self.states = getattr(app, "analog_simulations", {})
        app.analog_simulations = self.states
        if not hasattr(app, "analog_profile_running"):
            app.analog_profile_running = {}
        self.scheduler_job = None
        self.shutting_down = False
        self.tick_count = 0
        self.write_count = 0
        self.deferred_write_count = 0
        self.last_tick_duration_ms = 0.0
        self.max_tick_duration_ms = 0.0
        self._last_capacity_warning = 0.0

    @property
    def active_count(self):
        return sum(state.running for state in self.states.values())

    @property
    def callback_count(self):
        return int(self.scheduler_job is not None)

    def start(self, tag, configuration=None, *, schedule=True):
        if configuration is not None:
            update_canonical_analog_profile(self.app, tag, configuration)
        configuration = canonical_analog_profile(self.app, tag)
        parsed = _parse_configuration(configuration)
        now = self.clock()
        current = self.app.tag_runtime.get_value(tag.name, parsed["minimum"])
        try:
            current = float(current)
        except (TypeError, ValueError):
            current = parsed["minimum"]
        state = AnalogSimulationState(
            tag=tag,
            running=True,
            mode=parsed["mode"],
            current_value=current,
            minimum=parsed["minimum"],
            maximum=parsed["maximum"],
            step=parsed["step"],
            interval_ms=parsed["interval_ms"],
            next_update_time=now,
            started_at=now,
        )
        self.states[tag.name] = state
        getattr(self.app, "analog_profile_running", {})[tag.name] = True
        self._notify_status(tag.name)
        if schedule:
            self._ensure_scheduler()
        return state

    def start_many(self, items):
        started = []
        for tag, configuration in items:
            started.append(self.start(tag, configuration, schedule=False))
        self._ensure_scheduler()
        return started

    def stop(self, tag_name):
        state = self.states.get(tag_name)
        if state is not None:
            state.running = False
        getattr(self.app, "analog_profile_running", {})[tag_name] = False
        self._notify_status(tag_name)
        if not self._needs_scheduler():
            self._cancel_scheduler()

    def stop_all(self):
        for tag_name, state in self.states.items():
            state.running = False
            getattr(self.app, "analog_profile_running", {})[tag_name] = False
        self._cancel_scheduler()
        self._notify_status(getattr(self.app, "_analog_selected_tag_name", None))

    def shutdown(self):
        self.shutting_down = True
        self.stop_all()

    def reconcile(self, tags):
        """Stop removed or incompatible tags after a model rebuild."""
        current = {tag.name: tag for tag in tags}
        for tag_name, state in tuple(self.states.items()):
            tag = current.get(tag_name)
            if (
                tag is None
                or not tag.enabled_sim
                or tag.data_type not in ("INT", "REAL")
                or tag.direction != "Input"
                or (tag.data_type, tag.address) != (
                    state.tag.data_type, state.tag.address
                )
            ):
                self.stop(tag_name)
            else:
                state.tag = tag

    def tick(self, now=None, *, reschedule=True):
        started = time.perf_counter()
        if self.shutting_down or getattr(self.app, "is_closing", False) or getattr(
            self.app, "_shutdown_started", False
        ):
            self._cancel_scheduler()
            return 0
        now = self.clock() if now is None else now
        due = [
            state
            for state in self.states.values()
            if state.running
            and state.mode != "Manual"
            and state.next_update_time <= now
        ]
        writes = 0
        for state in due[: self.max_writes_per_tick]:
            next_value = _next_value(state)
            result = self.app.write_analog_tag(state.tag, next_value, notify=False)
            if result is None:
                self.stop(state.tag.name)
                self._notify_status(state.tag.name, error=True)
                continue
            try:
                state.current_value = float(result)
            except (TypeError, ValueError):
                state.current_value = float(next_value)
            state.phase += 1
            state.last_update_time = now
            state.elapsed_ms = (now - state.started_at) * 1000.0
            state.next_update_time = now + state.interval_ms / 1000.0
            writes += 1
        deferred = max(0, len(due) - self.max_writes_per_tick)
        if deferred:
            self.deferred_write_count += deferred
            if now - self._last_capacity_warning >= 5.0:
                LOGGER.warning(
                    "Analog scheduler capacity reached: due=%d processed=%d deferred=%d",
                    len(due), writes, deferred,
                )
                self._last_capacity_warning = now
        self.tick_count += 1
        self.write_count += writes
        self.last_tick_duration_ms = (time.perf_counter() - started) * 1000.0
        self.max_tick_duration_ms = max(
            self.max_tick_duration_ms, self.last_tick_duration_ms
        )
        if reschedule:
            self._ensure_scheduler()
        return writes

    def _scheduled_tick(self):
        self.scheduler_job = None
        self.tick()

    def _needs_scheduler(self):
        return any(
            state.running and state.mode != "Manual"
            for state in self.states.values()
        )

    def _ensure_scheduler(self):
        if (
            self.scheduler_job is not None
            or self.shutting_down
            or not self._needs_scheduler()
            or getattr(self.app, "is_closing", False)
            or getattr(self.app, "_shutdown_started", False)
        ):
            return
        schedule = getattr(self.app, "schedule_job", None)
        if schedule is not None:
            self.scheduler_job = schedule(self.tick_ms, self._scheduled_tick)

    def ensure_scheduler(self):
        self._ensure_scheduler()

    def _cancel_scheduler(self):
        job = self.scheduler_job
        self.scheduler_job = None
        if job is not None:
            cancel = getattr(self.app, "cancel_job", None)
            if cancel is not None:
                cancel(job)

    def _notify_status(self, tag_name, error=False):
        callback = getattr(self.app, "refresh_analog_simulation_status", None)
        if callback is not None and tag_name:
            callback(tag_name, error=error)


def _parse_configuration(configuration):
    mode = str(configuration.get("mode", "Manual"))
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported analog profile mode: {mode}")
    minimum = float(configuration.get("min", 0))
    maximum = float(configuration.get("max", 27648))
    if minimum > maximum:
        raise ValueError("Analog profile minimum exceeds maximum")
    step = max(float(configuration.get("step", 1)), 1.0)
    interval_ms = max(int(configuration.get("interval_ms", 500)), MIN_INTERVAL_MS)
    return {
        "mode": mode,
        "minimum": minimum,
        "maximum": maximum,
        "step": step,
        "interval_ms": interval_ms,
    }


def _next_value(state):
    current = state.current_value
    if state.mode == "Ramp":
        value = current + state.step * state.direction
        if value >= state.maximum:
            value = state.maximum
            state.direction = -1
        elif value <= state.minimum:
            value = state.minimum
            state.direction = 1
        return value
    if state.mode == "Random":
        return state.random_generator.randint(
            int(state.minimum), int(state.maximum)
        )
    if state.mode == "Step":
        return state.maximum if current <= state.minimum else state.minimum
    return current


def ensure_analog_simulation_manager(app):
    manager = getattr(app, "analog_simulation_manager", None)
    if manager is None:
        manager = AnalogSimulationManager(app)
        app.analog_simulation_manager = manager
    return manager


def editor_configuration(item):
    return {
        "mode": item["profile_mode"].get(),
        "min": item["min_entry"].get(),
        "max": item["max_entry"].get(),
        "step": item["step_entry"].get(),
        "interval_ms": item["interval_entry"].get(),
    }


def start_profile(app, index):
    if getattr(app, "is_rebuilding", False):
        return None
    tag = app.analog_tags[index]
    try:
        state = ensure_analog_simulation_manager(app).start(tag)
    except ValueError:
        item = app.analog_controls[index]
        item["profile_status"].configure(text="ERRO", text_color="orange")
        return None
    return state


def stop_profile(app, index):
    if index >= len(app.analog_tags):
        return
    ensure_analog_simulation_manager(app).stop(app.analog_tags[index].name)


def run_profile(app, index):
    """Compatibility entry point retained for older callers and tests."""
    if getattr(app, "is_closing", False) or getattr(app, "_shutdown_started", False):
        return
    manager = getattr(app, "analog_simulation_manager", None)
    if manager is not None:
        manager.tick()
