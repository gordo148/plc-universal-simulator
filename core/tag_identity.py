"""Stable identity utilities for tag definitions."""

from __future__ import annotations

import uuid


class InvalidTagIdError(ValueError):
    """Raised when an explicitly supplied tag ID is not a UUID v4."""


def generate_tag_id() -> str:
    """Return a new canonical lowercase UUID v4 string."""
    return str(uuid.uuid4())


def normalize_tag_id(value) -> str:
    """Return *value* as canonical UUID v4 text or raise a clear error."""
    if value is None:
        raise InvalidTagIdError("Tag ID must be a valid UUID v4, not None.")

    try:
        candidate = value if isinstance(value, uuid.UUID) else uuid.UUID(
            str(value).strip()
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise InvalidTagIdError("Tag ID must be a valid UUID v4.") from error

    if candidate.version != 4 or candidate.variant != uuid.RFC_4122:
        raise InvalidTagIdError("Tag ID must be an RFC 4122 UUID v4.")
    return str(candidate)


def is_valid_tag_id(value) -> bool:
    """Return whether *value* can be normalized as an RFC 4122 UUID v4."""
    try:
        normalize_tag_id(value)
    except InvalidTagIdError:
        return False
    return True
