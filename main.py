import logging
import os
import sys
import threading
import time

from core.version import APP_NAME, APP_VERSION
from services.logger_service import configure_logging

STARTUP_STARTED = time.perf_counter()
LOGGER = configure_logging()

from ui.main_window import PLCSimulator  # noqa: E402


LOGGER = logging.getLogger("plc_universal_simulator.startup")


def _log_unexpected_exception(exception_type, exception, traceback):
    if issubclass(exception_type, KeyboardInterrupt):
        sys.__excepthook__(exception_type, exception, traceback)
        return
    LOGGER.critical(
        "Unexpected application exception",
        exc_info=(exception_type, exception, traceback),
    )


def _log_startup_metrics():
    elapsed = time.perf_counter() - STARTUP_STARTED
    try:
        import resource

        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_rss_mb = (
            peak_rss / (1024 * 1024)
            if sys.platform == "darwin"
            else peak_rss / 1024
        )
        LOGGER.info(
            "Application ready in %.3f s (peak RSS %.1f MiB)",
            elapsed,
            peak_rss_mb,
        )
    except (ImportError, OSError):
        LOGGER.info("Application ready in %.3f s", elapsed)


def _configure_shutdown_integration(simulator):
    """Opt-in packaged/source lifecycle driver used by the timeout script."""
    mode = os.environ.get("PLC_SHUTDOWN_INTEGRATION")
    if not mode:
        return
    def drive():
        from ui.project_config import open_project_path
        from ui.trend_tab import start_trend, stop_trend
        import ui.main_window as main_window
        project = os.environ.get("PLC_SHUTDOWN_PROJECT", "configs/EDPGER02.simproject")
        if project and not open_project_path(simulator, project):
            raise RuntimeError(f"could not open project: {project}")
        if project:
            simulator._after_project_opened()
        for brand in ("Siemens", "Simulator", "Schneider", "Siemens"):
            simulator.brand_menu.set(brand); simulator.update_brand(brand)
        if os.environ.get("PLC_SHUTDOWN_CONNECT") == "1":
            from ui.header import set_connection_value
            connect_ip = os.environ.get("PLC_SHUTDOWN_CONNECT_IP")
            if connect_ip: set_connection_value(simulator, "ip", connect_ip)
            simulator.connect()
        for tab in ("Dashboard", "Entradas Digitais", "Entradas Analógicas", "Trends"):
            simulator.tabs.set(tab); simulator._on_tab_changed()
        simulator.ensure_trend_tab(); start_trend(simulator); stop_trend(simulator)
        if os.environ.get("PLC_SHUTDOWN_DIRTY") == "1": simulator.mark_project_dirty()
        else: simulator._mark_project_saved()
        if mode in ("accept", "cancel"):
            answer = mode == "accept"
            main_window.messagebox.askyesno = lambda *_a, **_k: answer
        print("CLOSE_INITIATED", flush=True)
        simulator.app.after(100, simulator.on_close)
        if mode == "cancel": simulator.app.after(1000, simulator.app.destroy)
    simulator.app.after(0, drive)


if __name__ == "__main__":
    sys.excepthook = _log_unexpected_exception
    LOGGER.info("%s v%s startup", APP_NAME, APP_VERSION)
    try:
        simulator = PLCSimulator()
        _configure_shutdown_integration(simulator)
        _log_startup_metrics()
        simulator.run()
    finally:
        LOGGER.warning(
            "%.6f PROCESS EXIT thread=%s",
            time.monotonic(),
            threading.current_thread().name,
        )
        for handler in logging.getLogger().handlers:
            handler.flush()
        LOGGER.info("Application shutdown")
