import logging
import sys
import time

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


if __name__ == "__main__":
    sys.excepthook = _log_unexpected_exception
    LOGGER.info("Application startup")
    try:
        simulator = PLCSimulator()
        _log_startup_metrics()
        simulator.run()
    finally:
        LOGGER.info("Application shutdown")
