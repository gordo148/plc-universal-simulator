import logging

from services.logger_service import configure_logging


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
