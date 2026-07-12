#!/usr/bin/env python3
"""Profile repeatable PLC Simulator shutdown scenarios without a physical PLC."""

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.tag_model import TagDefinition
from ui.main_window import PLCSimulator
from ui.project_config import _write_project
from ui.tag_manager import refresh_tag_table


def tags_for(count, trend=False):
    return [
        TagDefinition(
            f"Tag{i:05d}", "BOOL", "Input", f"DBX{i // 8}.{i % 8}",
            enabled_sim=True, enabled_trend=trend,
        )
        for i in range(count)
    ]


def prepare(count, active_simulator=False, trends=False):
    app = PLCSimulator()
    app.tags = tags_for(count, trend=trends)
    app.tag_runtime.sync(app.tags)
    app.ensure_tag_manager_tab()
    refresh_tag_table(app)
    if trends:
        app.ensure_trend_tab()
    if active_simulator:
        app.brand_menu.set("Simulator")
        app.update_brand("Simulator")
        app.connect()
    settings_path = tempfile.mktemp(prefix="plc-settings-", suffix=".json")
    original_save = app.settings.save
    app.settings.save = lambda: original_save(settings_path)
    app._mark_project_saved()
    return app, settings_path


def legacy_close(app):
    phases = {}
    total = time.perf_counter()
    def phase(name, callback):
        started = time.perf_counter(); callback()
        phases[name] = (time.perf_counter() - started) * 1000
    phase("tag_serialization", app.has_unsaved_changes)
    phase("stop_polling", lambda: setattr(app, "cyclic_read_enabled", False))
    phase("cancel_callbacks", app.cancel_pending_tab_refreshes)
    phase("cancel_remaining_callbacks", app.cancel_pending_jobs)
    phase("plc_disconnect", app.plc_service.disconnect)
    phase("settings_save", app._save_settings)
    phase("root_destroy", app.app.destroy)
    phases["total"] = (time.perf_counter() - total) * 1000
    return phases


def run_case(count, mode, active_simulator=False, trends=False, dirty=False):
    app, settings_path = prepare(count, active_simulator, trends)
    project_save_ms = 0.0
    project_writes = 0
    project_path = None
    try:
        if dirty:
            app.tags[0].address = "DBX999.0" if app.tags else ""
            app.mark_project_dirty()
            descriptor, project_path = tempfile.mkstemp(suffix=".simproject")
            os.close(descriptor)
            started = time.perf_counter()
            if _write_project(app, project_path):
                project_writes = 1
                app._mark_project_saved()
            project_save_ms = (time.perf_counter() - started) * 1000
        if mode == "legacy":
            timings = legacy_close(app)
        else:
            app.on_close()
            timings = app._shutdown_timings
        return {
            "tags": count, "mode": mode, "active_simulator": active_simulator,
            "trends_initialized": trends, "dirty_project_saved": dirty,
            "project_save_ms": round(project_save_ms, 3),
            "project_file_writes": project_writes,
            "shutdown": {key: round(value, 3) for key, value in timings.items()},
        }
    finally:
        for path in (settings_path, project_path):
            if path:
                try: os.unlink(path)
                except OSError: pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("legacy", "current"), default="current")
    parser.add_argument("--counts", nargs="*", type=int, default=[0, 100, 1000, 5000])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not os.environ.get("DISPLAY"):
        parser.error("DISPLAY is required; use a desktop session or xvfb-run -a")
    results = [run_case(count, args.mode) for count in args.counts]
    results.append(run_case(1000, args.mode, active_simulator=True, trends=True, dirty=True))
    payload = {"mode": args.mode, "results": results}
    rendered = json.dumps(payload, indent=2)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
