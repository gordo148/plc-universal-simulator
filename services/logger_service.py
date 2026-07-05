"""Application logging configuration."""

from __future__ import annotations

import logging
from pathlib import Path
import sys


LOG_FILENAME = "plc_simulator.log"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def default_log_path() -> Path:
    """Return the desktop application's log file location."""
    if getattr(sys, "frozen", False):
        base_directory = Path(sys.executable).resolve().parent
    else:
        base_directory = Path(__file__).resolve().parent.parent
    return base_directory / "logs" / LOG_FILENAME


def configure_logging(log_path=None) -> logging.Logger:
    """Configure file logging once and return the application logger."""
    destination = Path(log_path) if log_path else default_log_path()
    destination.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    resolved_destination = destination.resolve()

    for handler in root_logger.handlers:
        if (
            getattr(handler, "_plc_simulator_file_handler", False)
            and Path(handler.baseFilename).resolve() == resolved_destination
        ):
            return logging.getLogger("plc_universal_simulator")

    file_handler = logging.FileHandler(destination, encoding="utf-8")
    file_handler._plc_simulator_file_handler = True
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(file_handler)

    if not any(
        getattr(handler, "_plc_simulator_console_handler", False)
        for handler in root_logger.handlers
    ):
        console_handler = logging.StreamHandler()
        console_handler._plc_simulator_console_handler = True
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root_logger.addHandler(console_handler)

    return logging.getLogger("plc_universal_simulator")
