#!/usr/bin/env python3
"""Drive a real Tk shutdown workflow under an external process timeout."""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.logger_service import configure_logging

configure_logging()

from ui.main_window import PLCSimulator
from ui.header import set_connection_value
from ui.project_config import open_project_path
from ui.trend_tab import start_trend, stop_trend
import ui.main_window as main_window


def drive(args):
    app = PLCSimulator()
    if args.project:
        if not open_project_path(app, args.project):
            raise RuntimeError(f"could not open project: {args.project}")
        app._after_project_opened()
    for brand in ("Siemens", "Simulator", "Schneider", "Siemens"):
        app.brand_menu.set(brand)
        app.update_brand(brand)
    if args.connect:
        if args.connect_ip:
            set_connection_value(app, "ip", args.connect_ip)
        app.connect()
    for tab in ("Dashboard", "Entradas Digitais", "Entradas Analógicas", "Trends"):
        app.tabs.set(tab)
        app._on_tab_changed()
    app.ensure_trend_tab()
    start_trend(app)
    stop_trend(app)
    if args.dirty:
        app.mark_project_dirty()
    else:
        app._mark_project_saved()

    if args.confirm != "real":
        answer = args.confirm == "accept"
        main_window.messagebox.askyesno = lambda *_a, **_k: answer

    print("CLOSE_INITIATED", flush=True)
    app.app.after(100, app.on_close)
    if args.confirm == "cancel":
        app.app.after(500, app.on_close)
        app.app.after(1000, app.app.destroy)
    app.run()
    print(f"shutdown_returned confirm={args.confirm} dirty={args.dirty}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="configs/EDPGER02.simproject")
    parser.add_argument("--confirm", choices=("real", "accept", "cancel"), default="accept")
    parser.add_argument("--dirty", action="store_true")
    parser.add_argument("--connect", action="store_true")
    parser.add_argument("--connect-ip")
    drive(parser.parse_args())


if __name__ == "__main__":
    main()
