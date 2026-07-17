"""Application logging configuration."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


LOG_FILENAME = "plc_simulator.log"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
LOG_MAX_SIZE_MB = 5
LOG_BACKUP_COUNT = 5
_BYTES_PER_MEBIBYTE = 1024 * 1024


def default_log_path() -> Path:
    """Return the desktop application's log file location."""
    if getattr(sys, "frozen", False):
        base_directory = Path(sys.executable).resolve().parent
    else:
        base_directory = Path(__file__).resolve().parent.parent
    return base_directory / "logs" / LOG_FILENAME


def configure_logging(log_path=None) -> logging.Logger:
    """Configure rotating file logging once and return the application logger."""
    destination = Path(log_path) if log_path else default_log_path()

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if not any(
        getattr(handler, "_plc_simulator_console_handler", False)
        for handler in root_logger.handlers
    ):
        console_handler = logging.StreamHandler()
        console_handler._plc_simulator_console_handler = True
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root_logger.addHandler(console_handler)

    application_logger = logging.getLogger("plc_universal_simulator")

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        resolved_destination = destination.resolve()
    except OSError as exc:
        application_logger.warning(
            "Unable to prepare log file %s: %s", destination, exc
        )
        return application_logger

    for handler in root_logger.handlers:
        if (
            getattr(handler, "_plc_simulator_file_handler", False)
            and Path(handler.baseFilename).resolve() == resolved_destination
        ):
            return application_logger

    try:
        file_handler = RotatingFileHandler(
            destination,
            maxBytes=LOG_MAX_SIZE_MB * _BYTES_PER_MEBIBYTE,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError as exc:
        application_logger.warning(
            "Unable to open log file %s: %s", destination, exc
        )
        return application_logger

    file_handler._plc_simulator_file_handler = True
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(file_handler)

    return application_logger
