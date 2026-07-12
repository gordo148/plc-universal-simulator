#!/usr/bin/env python3
"""Repeatable Trends master-detail benchmark; no PLC is required."""

import argparse
import json
import os
import sys
import time
import tracemalloc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.tag_model import TagDefinition
from ui.main_window import PLCSimulator
from ui.trend_tab import bind_selected_trend, refresh_trend_selectors, update_trend_table_values


def tags_for(count):
    kinds = ("BOOL", "INT", "REAL")
    return [TagDefinition(f"Trend_{index:05d}", kinds[index % 3], "Input", f"DB{index // 100}.{index % 100}", enabled_trend=True) for index in range(count)]


def timed(callback):
    started = time.perf_counter(); callback(); return (time.perf_counter() - started) * 1000


def descendants(widget):
    result = []
    for child in widget.winfo_children():
        result.append(child); result.extend(descendants(child))
    return result


def run(count):
    tracemalloc.start(); started = time.perf_counter(); app = PLCSimulator(); app_startup_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter(); app.tags = tags_for(count); model_ms = (time.perf_counter() - started) * 1000
    structure_ms = timed(lambda: (app.ensure_trend_tab(), app.app.update_idletasks()))
    widgets = descendants(app.tab_trends)
    widget_count = sum(type(widget).__module__.startswith("customtkinter") for widget in widgets)
    refresh_ms = timed(lambda: refresh_trend_selectors(app))
    app.trend_search_entry.insert(0, "Trend_04")
    search_ms = timed(lambda: refresh_trend_selectors(app))
    app.trend_search_entry.delete(0, "end"); app.trend_filter_menu.set("REAL")
    filter_ms = timed(lambda: refresh_trend_selectors(app))
    selection_ms = timed(lambda: bind_selected_trend(app))
    value_ms = timed(lambda: update_trend_table_values(app))
    chart_ms = timed(lambda: app.trend_canvas.draw_idle())
    _current, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    app._mark_project_saved()
    shutdown_ms = timed(app.on_close)
    return {"tags": count, "app_startup_ms": round(app_startup_ms, 3), "model_ms": round(model_ms, 3), "structure_ms": round(structure_ms, 3), "refresh_ms": round(refresh_ms, 3), "search_ms": round(search_ms, 3), "filter_ms": round(filter_ms, 3), "selection_ms": round(selection_ms, 3), "value_refresh_ms": round(value_ms, 3), "chart_refresh_ms": round(chart_ms, 3), "shutdown_ms": round(shutdown_ms, 3), "ctk_structure_count": widget_count, "per_tag_tk_variables": len(app.trend_tag_vars), "peak_memory_mb": round(peak / 1024 / 1024, 3)}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--counts", nargs="+", type=int, default=[100, 1000, 5000]); parser.add_argument("--output")
    args = parser.parse_args(); results = [run(count) for count in args.counts]; output = json.dumps(results, indent=2); print(output)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as stream: stream.write(output + "\n")


if __name__ == "__main__": main()
