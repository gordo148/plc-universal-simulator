import logging
from logging.handlers import RotatingFileHandler

import pytest

import services.logger_service as logger_service
from services.logger_service import (
    LOG_BACKUP_COUNT,
    LOG_FORMAT,
    LOG_MAX_SIZE_MB,
    configure_logging,
)


@pytest.fixture(autouse=True)
def isolated_application_handlers():
    root_logger = logging.getLogger()
    original_level = root_logger.level

    def remove_application_handlers():
        for handler in list(root_logger.handlers):
            if getattr(handler, "_plc_simulator_file_handler", False) or getattr(
                handler, "_plc_simulator_console_handler", False
            ):
                root_logger.removeHandler(handler)
                handler.close()

    remove_application_handlers()
    yield
    remove_application_handlers()
    root_logger.setLevel(original_level)


def application_handlers():
    return [
        handler
        for handler in logging.getLogger().handlers
        if getattr(handler, "_plc_simulator_file_handler", False)
        or getattr(handler, "_plc_simulator_console_handler", False)
    ]


def rotating_handler():
    return next(
        handler
        for handler in application_handlers()
        if getattr(handler, "_plc_simulator_file_handler", False)
    )


def test_logger_creates_directory_and_log_file(tmp_path):
    log_path = tmp_path / "logs" / "plc_simulator.log"

    logger = configure_logging(log_path)
    logger.info("release candidate logger test")
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert log_path.is_file()
    assert "release candidate logger test" in log_path.read_text(
        encoding="utf-8"
    )


def test_logger_installs_rotating_file_handler_with_expected_configuration(
    tmp_path,
):
    configure_logging(tmp_path / "plc_simulator.log")

    handler = rotating_handler()

    assert isinstance(handler, RotatingFileHandler)
    assert handler.encoding.lower().replace("-", "") == "utf8"
    assert handler.maxBytes == LOG_MAX_SIZE_MB * 1024 * 1024
    assert handler.backupCount == LOG_BACKUP_COUNT
    assert handler.formatter._fmt == LOG_FORMAT


def test_logger_initialization_is_idempotent(tmp_path):
    log_path = tmp_path / "plc_simulator.log"

    logger = configure_logging(log_path)
    first_handlers = application_handlers()
    configure_logging(log_path)

    assert application_handlers() == first_handlers

    logger.info("one message")
    rotating_handler().flush()
    assert log_path.read_text(encoding="utf-8").count("one message") == 1


def test_console_logging_remains_enabled(tmp_path, capsys):
    logger = configure_logging(tmp_path / "plc_simulator.log")

    logger.warning("console warning")

    assert "console warning" in capsys.readouterr().err


def test_logger_reuses_existing_log_directory(tmp_path):
    log_directory = tmp_path / "logs"
    log_directory.mkdir()

    logger = configure_logging(log_directory / "plc_simulator.log")
    logger.info("existing directory")
    rotating_handler().flush()

    assert (log_directory / "plc_simulator.log").is_file()


def test_logger_falls_back_to_console_when_directory_cannot_be_created(
    tmp_path, capsys
):
    blocked_directory = tmp_path / "blocked"
    blocked_directory.write_text("not a directory", encoding="utf-8")

    logger = configure_logging(blocked_directory / "plc_simulator.log")

    assert logger.name == "plc_universal_simulator"
    assert not any(
        getattr(handler, "_plc_simulator_file_handler", False)
        for handler in application_handlers()
    )
    assert "Unable to prepare log file" in capsys.readouterr().err


def test_logger_falls_back_to_console_when_log_file_cannot_be_opened(
    tmp_path, capsys, monkeypatch
):
    def fail_to_open(*args, **kwargs):
        raise OSError("read-only destination")

    monkeypatch.setattr(logger_service, "RotatingFileHandler", fail_to_open)

    logger = configure_logging(tmp_path / "plc_simulator.log")

    assert logger.name == "plc_universal_simulator"
    assert not any(
        getattr(handler, "_plc_simulator_file_handler", False)
        for handler in application_handlers()
    )
    assert "Unable to open log file" in capsys.readouterr().err


def test_rotating_handler_creates_backup_file(tmp_path):
    log_path = tmp_path / "plc_simulator.log"
    logger = configure_logging(log_path)
    handler = rotating_handler()
    handler.maxBytes = 128

    for index in range(10):
        logger.info("rotation message %s %s", index, "x" * 80)
    handler.flush()

    assert log_path.is_file()
    assert (tmp_path / "plc_simulator.log.1").is_file()
