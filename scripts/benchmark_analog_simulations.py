#!/usr/bin/env python3
"""Benchmark the central analog scheduler without constructing UI widgets."""

import argparse
import json
from pathlib import Path
import sys
import time
import tracemalloc
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.tag_model import TagDefinition
from core.tag_runtime import RuntimeTagCache
from services.plc_service import PLCService
from ui.analog_profiles import AnalogSimulationManager


def _configuration(index):
    modes = ("Ramp", "Step", "Random", "Manual")
    return {
        "mode": modes[index % len(modes)],
        "min": 0,
        "max": 27648,
        "step": index % 50 + 1,
        "interval_ms": 500,
    }


def benchmark(active_count, configured_count=1000):
    tags = [
        TagDefinition(f"Analog_{index}", "REAL", "Input", f"A{index}", True)
        for index in range(configured_count)
    ]
    cache = RuntimeTagCache()
    cache.sync(tags)
    service = PLCService(runtime_cache=cache)
    if not service.connect("Simulator", ""):
        raise RuntimeError("Internal Simulator connection failed")
    callbacks = {}
    next_job = 0
    app = SimpleNamespace(
        tag_runtime=cache,
        analog_profile_running={},
        analog_simulations={},
        is_closing=False,
        _shutdown_started=False,
    )

    def schedule_job(_delay, callback):
        nonlocal next_job
        next_job += 1
        job = f"after-{next_job}"
        callbacks[job] = callback
        return job

    def cancel_job(job):
        callbacks.pop(job, None)

    def write_analog_tag(tag, value, notify=False):
        return service.write_numeric(tag, value)

    app.schedule_job = schedule_job
    app.cancel_job = cancel_job
    app.write_analog_tag = write_analog_tag
    manager = AnalogSimulationManager(
        app, max_writes_per_tick=100, clock=lambda: 0.0
    )
    app.analog_simulation_manager = manager

    tracemalloc.start()
    manager.start_many(
        (tag, _configuration(index))
        for index, tag in enumerate(tags[:active_count])
    )
    start = time.perf_counter()
    dynamic_count = sum(
        state.mode != "Manual" for state in manager.states.values()
    )
    while manager.write_count < dynamic_count:
        manager.tick(now=0.0, reschedule=False)
    scheduler_elapsed = time.perf_counter() - start

    refresh_started = time.perf_counter()
    visible_values = [cache.get_value(tag.name) for tag in tags[:50]]
    visible_refresh_ms = (time.perf_counter() - refresh_started) * 1000.0
    _ = visible_values
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    active_callback_count = len(callbacks)

    shutdown_started = time.perf_counter()
    manager.shutdown()
    service.disconnect()
    shutdown_ms = (time.perf_counter() - shutdown_started) * 1000.0
    return {
        "configured_tags": configured_count,
        "active_simulations": active_count,
        "dynamic_profiles": dynamic_count,
        "scheduler_callbacks_active": active_callback_count,
        "scheduler_callbacks_after_shutdown": len(callbacks),
        "scheduler_ticks": manager.tick_count,
        "writes": manager.write_count,
        "writes_per_second": (
            manager.write_count / scheduler_elapsed if scheduler_elapsed else 0.0
        ),
        "last_tick_ms": manager.last_tick_duration_ms,
        "max_tick_ms": manager.max_tick_duration_ms,
        "visible_50_refresh_ms": visible_refresh_ms,
        "peak_memory_mib": peak / (1024 * 1024),
        "shutdown_ms": shutdown_ms,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--counts", nargs="+", type=int, default=[10, 100, 500])
    parser.add_argument("--configured", type=int, default=1000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    results = [benchmark(count, args.configured) for count in args.counts]
    payload = json.dumps(results, indent=2)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
