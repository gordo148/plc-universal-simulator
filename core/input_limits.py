"""Defensive limits for files loaded completely into memory."""

from __future__ import annotations

import logging
from pathlib import Path


_MEBIBYTE = 1024 * 1024

# Generous limits for legitimate simulator projects and industrial CSV exports.
MAX_PROJECT_FILE_SIZE_BYTES = 50 * _MEBIBYTE
MAX_CSV_FILE_SIZE_BYTES = 25 * _MEBIBYTE

LOGGER = logging.getLogger(__name__)


class InputFileTooLargeError(ValueError):
    """Raised before reading an input file that exceeds its configured limit."""

    def __init__(self, path, actual_size, maximum_size, file_category):
        self.path = Path(path)
        self.actual_size = int(actual_size)
        self.maximum_size = int(maximum_size)
        self.file_category = str(file_category)
        super().__init__(
            f"{self.file_category} file exceeds the maximum supported size "
            f"({self.actual_size} bytes; limit {self.maximum_size} bytes)."
        )


def validate_input_file_size(path, maximum_size, file_category):
    """Return a normalized path after validating its metadata-reported size."""
    normalized_path = Path(path)
    actual_size = normalized_path.stat().st_size
    if actual_size > maximum_size:
        LOGGER.warning(
            "Input file rejected: category=%s path=%s size_bytes=%d "
            "limit_bytes=%d",
            file_category,
            normalized_path,
            actual_size,
            maximum_size,
        )
        raise InputFileTooLargeError(
            normalized_path,
            actual_size,
            maximum_size,
            file_category,
        )
    return normalized_path
