import logging
import sys
import time


STARTUP_STARTED = time.perf_counter()

from ui.main_window import PLCSimulator  # noqa: E402


LOGGER = logging.getLogger("plc_universal_simulator.startup")


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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    simulator = PLCSimulator()
    _log_startup_metrics()
    simulator.run()
