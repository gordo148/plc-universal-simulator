from dataclasses import dataclass
from enum import Enum
import time
from typing import Any, Iterable

from core.tag_model import TagDefinition


class RuntimeValueSource(str, Enum):
    PLC = "PLC"
    SIMULATION = "SIMULATION"


@dataclass
class TagRuntime:
    value: Any = None
    valid: bool = False
    updated_at: float | None = None
    source: RuntimeValueSource | None = None


class RuntimeTagCache:
    """Central store for volatile values, keyed by tag definition name."""

    def __init__(self) -> None:
        self._values: dict[str, TagRuntime] = {}
        self._definitions: dict[str, tuple[str, str, str]] = {}

    def sync(self, definitions: Iterable[TagDefinition]) -> None:
        next_values = {}
        next_definitions = {}

        for tag in definitions:
            signature = (
                str(tag.data_type).strip().upper(),
                str(tag.direction).strip(),
                str(tag.address).strip().upper(),
            )
            next_definitions[tag.name] = signature
            if self._definitions.get(tag.name) == signature:
                next_values[tag.name] = self._values.get(
                    tag.name,
                    TagRuntime(),
                )
            else:
                next_values[tag.name] = TagRuntime()

        self._values = next_values
        self._definitions = next_definitions

    def update(
        self,
        name: str,
        value: Any,
        source: RuntimeValueSource = RuntimeValueSource.SIMULATION,
    ) -> None:
        runtime = self._values.setdefault(name, TagRuntime())
        runtime.value = value
        runtime.valid = True
        runtime.updated_at = time.time()
        runtime.source = source

    def invalidate(self, name: str) -> None:
        runtime = self._values.setdefault(name, TagRuntime())
        runtime.valid = False
        runtime.updated_at = time.time()

    def invalidate_all(self) -> None:
        invalidated_at = time.time()
        for runtime in self._values.values():
            runtime.valid = False
            runtime.updated_at = invalidated_at

    def invalidate_source(self, source: RuntimeValueSource) -> None:
        invalidated_at = time.time()
        for runtime in self._values.values():
            if runtime.source == source:
                runtime.valid = False
                runtime.updated_at = invalidated_at

    def clear(self) -> None:
        """Discard all temporary runtime values."""
        self._values.clear()
        self._definitions.clear()

    def get(self, name: str) -> TagRuntime | None:
        return self._values.get(name)

    def get_value(self, name: str, default: Any = None) -> Any:
        runtime = self.get(name)
        if runtime is None or not runtime.valid:
            return default
        return runtime.value

    def snapshot(self) -> dict[str, TagRuntime]:
        return {
            name: TagRuntime(
                item.value,
                item.valid,
                item.updated_at,
                item.source,
            )
            for name, item in self._values.items()
        }
