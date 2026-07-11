#!/usr/bin/env python3
"""Repeatable Digital/Analog UI benchmark using synthetic tags.

Run with a real display or under Xvfb.  The benchmark never connects to a PLC.
"""

import argparse
import csv
import json
import os
import statistics
import sys
import time
import tempfile
import tracemalloc
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import customtkinter as ctk

from core.tag_model import TagDefinition
from core.tag_runtime import RuntimeTagCache
from ui import analog_tab, digital_tab
from ui.main_window import PLCSimulator
from ui.scrollable_frame import SafeScrollableFrame
from ui.tag_manager import TAG_CSV_FIELDS, read_tags_csv


WIDGET_TYPES = (
    "CTkFrame", "CTkLabel", "CTkButton", "CTkSlider", "CTkEntry",
    "CTkOptionMenu", "CTkScrollbar",
)


class UIProbe:
    def __init__(self):
        self.counts = Counter()
        self.constructor_seconds = defaultdict(float)
        self.layout_seconds = 0.0
        self.layout_calls = 0
        self.callbacks = 0
        self.bindings = 0
        self._originals = {}

    def __enter__(self):
        for name in WIDGET_TYPES:
            original = getattr(ctk, name)
            self._originals[name] = original

            def factory(*args, _name=name, _original=original, **kwargs):
                started = time.perf_counter()
                widget = _original(*args, **kwargs)
                self.constructor_seconds[_name] += time.perf_counter() - started
                self.counts[_name] += 1
                if callable(kwargs.get("command")):
                    self.callbacks += 1
                self._instrument_widget(widget)
                return widget

            setattr(ctk, name, factory)
        return self

    def _instrument_widget(self, widget):
        for method_name in ("pack", "grid", "place"):
            original = getattr(widget, method_name, None)
            if original is None:
                continue

            def measured(*args, _original=original, **kwargs):
                started = time.perf_counter()
                try:
                    return _original(*args, **kwargs)
                finally:
                    self.layout_seconds += time.perf_counter() - started
                    self.layout_calls += 1

            setattr(widget, method_name, measured)
        original_bind = getattr(widget, "bind", None)
        if original_bind is not None:
            def measured_bind(*args, **kwargs):
                self.bindings += 1
                return original_bind(*args, **kwargs)
            widget.bind = measured_bind

    def __exit__(self, *_args):
        for name, original in self._originals.items():
            setattr(ctk, name, original)


def synthetic_tags(kind, count):
    started = time.perf_counter()
    if kind == "digital":
        tags = [
            TagDefinition(f"D{i:05d}", "BOOL", "Input", f"M{i // 8}.{i % 8}", True)
            for i in range(count)
        ]
    else:
        tags = [
            TagDefinition(f"A{i:05d}", "REAL", "Input", f"DBD{i * 4}", True)
            for i in range(count)
        ]
    return tags, time.perf_counter() - started


def benchmark_csv_parse(count=1000):
    with tempfile.NamedTemporaryFile("w", suffix=".csv", newline="", delete=False) as handle:
        writer = csv.DictWriter(handle, fieldnames=TAG_CSV_FIELDS)
        writer.writeheader()
        for index in range(count):
            writer.writerow({
                "name": f"CSV_D{index}", "data_type": "BOOL", "direction": "Input",
                "address": f"M{index // 8}.{index % 8}", "enabled_sim": "1",
                "enabled_trend": "0", "enabled_alarm": "0", "enabled_dashboard": "0",
            })
        path = handle.name
    try:
        started = time.perf_counter()
        tags = read_tags_csv(path, "Simulator")
        elapsed = time.perf_counter() - started
    finally:
        os.unlink(path)
    return {"rows": len(tags), "parse_validate_time_ms": round(elapsed * 1000, 3)}


def make_app(root, tags):
    app = SimpleNamespace(
        app=root, tags=tags, tag_runtime=RuntimeTagCache(), is_closing=False,
        is_rebuilding=False, _pending_jobs=set(), _dirty_tabs=set(),
        digital_controls=[], digital_tags=[], digital_states={},
        pending_pulse_callbacks={}, analog_controls=[], analog_tags=[],
        analog_profile_running={}, analog_profile_directions={},
    )
    app.brand_menu = SimpleNamespace(get=lambda: "Simulator")
    app.schedule_job = lambda delay, callback: PLCSimulator.schedule_job(app, delay, callback)
    app.cancel_job = lambda job: PLCSimulator.cancel_job(app, job)
    app.digital_action = lambda _index: None
    app.update_digital_name = lambda _index: None
    app.update_analog = lambda _index, _value: None
    app.tab_digital = ctk.CTkFrame(root)
    app.tab_analog = ctk.CTkFrame(root)
    app.tab_digital.pack(fill="both", expand=True)
    app.tab_analog.pack(fill="both", expand=True)
    return app


def drain(root, predicate, timeout=30.0):
    deadline = time.perf_counter() + timeout
    while predicate():
        root.update()
        if time.perf_counter() > deadline:
            raise TimeoutError("UI generation did not finish")


def timed(root, callback, pending=lambda: False):
    started = time.perf_counter()
    callback()
    drain(root, pending)
    root.update_idletasks()
    return time.perf_counter() - started


def create_legacy_structure(app, kind, page_size):
    """Construct the pre-master-detail pooled-row benchmark fixture."""
    tab = app.tab_digital if kind == "digital" else app.tab_analog
    controls = ctk.CTkFrame(tab)
    controls.pack(fill="x")
    menu = ctk.CTkOptionMenu(controls, values=["25", "50", "100"])
    menu.set(str(page_size))
    menu.pack(side="left")
    previous = ctk.CTkButton(controls, text="Previous")
    following = ctk.CTkButton(controls, text="Next")
    loading = ctk.CTkLabel(controls, text="")
    for widget in (previous, following, loading):
        widget.pack(side="left")
    scroll = SafeScrollableFrame(tab)
    scroll.pack(fill="both", expand=True)
    scroll.install_navigation()
    if kind == "digital":
        app.digital_page = 0
        app.digital_page_size_menu = menu
        app.digital_previous_button, app.digital_next_button = previous, following
        app.digital_loading_label, app.digital_scroll = loading, scroll
        app.digital_row_pool, app._digital_after_jobs = [], set()
        app._digital_rebuilding = False
    else:
        app.analog_page = 0
        app.analog_page_size_menu = menu
        app.analog_previous_button, app.analog_next_button = previous, following
        app.analog_loading_label, app.analog_scroll = loading, scroll
        app.analog_search_entry = ctk.CTkEntry(controls)
        app.analog_search_entry.pack(side="left")
        app.analog_row_pool, app._analog_after_jobs = [], set()
        app._analog_rebuilding = False


def benchmark(kind, count, page_size, architecture="master-detail"):
    tags, model_seconds = synthetic_tags(kind, count)
    root = ctk.CTk()
    root.withdraw()
    heartbeat_times = []
    heartbeat_running = True

    def heartbeat():
        if heartbeat_running:
            heartbeat_times.append(time.perf_counter())
            root.after(10, heartbeat)

    root.after(10, heartbeat)
    tracemalloc.start()
    with UIProbe() as probe:
        app = make_app(root, tags)
        started = time.perf_counter()
        if architecture == "legacy":
            create_legacy_structure(app, kind, page_size)
        elif kind == "digital":
            digital_tab.create_digital_tab_structure(app)
            if not hasattr(app, "digital_scroll"):
                app.digital_scroll = SafeScrollableFrame(app.tab_digital)
                app.digital_scroll.pack(fill="both", expand=True)
                app.digital_scroll.install_navigation()
        else:
            analog_tab.create_analog_tab_structure(app)
            if not hasattr(app, "analog_scroll"):
                app.analog_scroll = SafeScrollableFrame(app.tab_analog)
                app.analog_scroll.pack(fill="both", expand=True)
                app.analog_scroll.install_navigation()
        root.update_idletasks()
        structure_seconds = time.perf_counter() - started

        menu = app.digital_page_size_menu if kind == "digital" else app.analog_page_size_menu
        menu.set(str(page_size))
        refresh = digital_tab.refresh_digital_visible_rows if kind == "digital" else analog_tab.refresh_analog_visible_rows
        rebuilding = (lambda: app._digital_rebuilding) if kind == "digital" else (lambda: app._analog_rebuilding)
        row_seconds = timed(root, lambda: refresh(app, reset_page=True), rebuilding)

        page_attr = "digital_page" if kind == "digital" else "analog_page"
        setattr(app, page_attr, 1 if count > page_size else 0)
        page_seconds = timed(root, lambda: refresh(app), rebuilding)

        menu.set("25")
        shrink_seconds = timed(root, lambda: refresh(app), rebuilding)

        started = time.perf_counter()
        if kind == "digital" and hasattr(app, "digital_table"):
            for index, tag in enumerate(app._digital_table_tags):
                app.tag_runtime.update(tag.name, bool(index % 2))
            digital_tab.update_digital_table_values(app)
            visible = len(app._digital_table_tags)
        elif kind == "analog" and hasattr(app, "analog_table"):
            for index, tag in enumerate(app._analog_table_tags):
                app.tag_runtime.update(tag.name, float(index))
            analog_tab.update_analog_table_values(app)
            visible = len(app._analog_table_tags)
        elif kind == "digital":
            for index in range(len(app.digital_controls)):
                PLCSimulator.update_digital_ui(app, index, bool(index % 2))
            visible = len(app.digital_controls)
        else:
            for index in range(len(app.analog_controls)):
                PLCSimulator.update_analog_ui(app, index, float(index))
            visible = len(app.analog_controls)
        root.update_idletasks()
        value_seconds = time.perf_counter() - started

        _, peak = tracemalloc.get_traced_memory()
        constructor_ms = {
            name: round(seconds * 1000, 3)
            for name, seconds in probe.constructor_seconds.items()
        }
        result = {
            "kind": kind, "architecture": architecture,
            "tags_total": count, "visible_rows": visible,
            "model_time_ms": round(model_seconds * 1000, 3),
            "structure_time_ms": round(structure_seconds * 1000, 3),
            "row_creation_time_ms": round(row_seconds * 1000, 3),
            "page_change_time_ms": round(page_seconds * 1000, 3),
            "page_size_50_to_25_ms": round(shrink_seconds * 1000, 3),
            "value_refresh_time_ms": round(value_seconds * 1000, 3),
            "widgets_created": sum(probe.counts.values()),
            "widgets_by_type": dict(probe.counts),
            "callbacks_registered": probe.callbacks + probe.bindings,
            "command_callbacks": probe.callbacks,
            "event_bindings": probe.bindings,
            "layout_calls": probe.layout_calls,
            "layout_time_ms": round(probe.layout_seconds * 1000, 3),
            "constructor_time_ms": constructor_ms,
            "peak_memory_mib": round(peak / 1024 / 1024, 3),
        }
    heartbeat_running = False
    if len(heartbeat_times) > 1:
        gaps = [b - a for a, b in zip(heartbeat_times, heartbeat_times[1:])]
        result["max_event_loop_gap_ms"] = round(max(gaps) * 1000, 3)
        result["median_event_loop_gap_ms"] = round(statistics.median(gaps) * 1000, 3)
    else:
        result["max_event_loop_gap_ms"] = None
        result["median_event_loop_gap_ms"] = None
    tracemalloc.stop()
    for callback_id in root.tk.call("after", "info"):
        try:
            root.after_cancel(callback_id)
        except Exception:
            pass
    root.destroy()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--digital", nargs="*", type=int, default=[100, 500, 1000, 5000])
    parser.add_argument("--analog", nargs="*", type=int, default=[100, 500, 1000])
    parser.add_argument("--architecture", choices=("master-detail", "legacy"), default="master-detail")
    args = parser.parse_args()
    if not os.environ.get("DISPLAY"):
        parser.error("DISPLAY is not set; run under a desktop session or xvfb-run -a")
    results = []
    for count in args.digital:
        results.append(benchmark("digital", count, 50, args.architecture))
    for count in args.analog:
        results.append(benchmark("analog", count, 25, args.architecture))
    document = {
        "python": sys.version.split()[0], "customtkinter": ctk.__version__,
        "display": os.environ.get("DISPLAY"), "csv_1000": benchmark_csv_parse(),
        "results": results,
    }
    rendered = json.dumps(document, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
