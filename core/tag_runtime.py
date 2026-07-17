from dataclasses import dataclass
from enum import Enum
import time
from typing import Any, Iterable

from core.tag_identity import normalize_tag_id
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


class DuplicateRuntimeTagIdError(ValueError):
    """Raised when one synchronized population contains a repeated tag ID."""


class AmbiguousTagNameError(LookupError):
    """Raised when a compatibility lookup matches more than one tag ID."""


class RuntimeTagCache:
    """Central volatile store keyed by stable ID, with name compatibility APIs."""

    def __init__(self) -> None:
        self._values: dict[str, TagRuntime] = {}
        self._definitions: dict[str, tuple[str, str, str]] = {}
        self._names: dict[str, str] = {}
        self._ids_by_name: dict[str, set[str]] = {}
        self._unbound_values: dict[str, TagRuntime] = {}

    def sync(self, definitions: Iterable[TagDefinition]) -> None:
        tags = list(definitions)
        normalized = []
        seen_ids = set()
        for tag in tags:
            tag_id = normalize_tag_id(tag.tag_id)
            if tag_id in seen_ids:
                raise DuplicateRuntimeTagIdError(
                    f'Duplicate runtime tag_id "{tag_id}" for tag "{tag.name}".'
                )
            seen_ids.add(tag_id)
            normalized.append((tag_id, tag))

        next_values: dict[str, TagRuntime] = {}
        next_definitions: dict[str, tuple[str, str, str]] = {}
        next_names: dict[str, str] = {}
        next_ids_by_name: dict[str, set[str]] = {}
        for tag_id, tag in normalized:
            signature = (
                str(tag.data_type).strip().upper(),
                str(tag.direction).strip(),
                str(tag.address).strip().upper(),
            )
            next_definitions[tag_id] = signature
            next_names[tag_id] = tag.name
            next_ids_by_name.setdefault(tag.name, set()).add(tag_id)
            if self._definitions.get(tag_id) == signature:
                next_values[tag_id] = self._values.get(tag_id, TagRuntime())
            else:
                next_values[tag_id] = TagRuntime()

        self._values = next_values
        self._definitions = next_definitions
        self._names = next_names
        self._ids_by_name = next_ids_by_name
        for name in next_ids_by_name:
            self._unbound_values.pop(name, None)

    def get_by_id(self, tag_id: str) -> TagRuntime | None:
        return self._values.get(normalize_tag_id(tag_id))

    def contains_id(self, tag_id: str) -> bool:
        return normalize_tag_id(tag_id) in self._values

    def update_by_id(
        self,
        tag_id: str,
        value: Any,
        source: RuntimeValueSource = RuntimeValueSource.SIMULATION,
    ) -> None:
        normalized = normalize_tag_id(tag_id)
        runtime = self._values.setdefault(normalized, TagRuntime())
        self._set_runtime_value(runtime, value, source)

    def invalidate_by_id(self, tag_id: str) -> None:
        normalized = normalize_tag_id(tag_id)
        self._invalidate_runtime(self._values.setdefault(normalized, TagRuntime()))

    def get_by_name(self, name: str) -> TagRuntime | None:
        tag_ids = self._ids_by_name.get(str(name), set())
        if len(tag_ids) > 1:
            raise AmbiguousTagNameError(
                f'Tag name "{name}" matches multiple runtime identities.'
            )
        if tag_ids:
            return self._values.get(next(iter(tag_ids)))
        return self._unbound_values.get(str(name))

    def update(
        self,
        tag_or_name: TagDefinition | str,
        value: Any,
        source: RuntimeValueSource = RuntimeValueSource.SIMULATION,
    ) -> None:
        if isinstance(tag_or_name, TagDefinition):
            tag_id = self._bind_tag(tag_or_name)
            self.update_by_id(tag_id, value, source)
            return
        name = str(tag_or_name)
        tag_ids = self._ids_by_name.get(name, set())
        if len(tag_ids) > 1:
            raise AmbiguousTagNameError(
                f'Tag name "{name}" matches multiple runtime identities.'
            )
        if tag_ids:
            self.update_by_id(next(iter(tag_ids)), value, source)
            return
        runtime = self._unbound_values.setdefault(name, TagRuntime())
        self._set_runtime_value(runtime, value, source)

    @staticmethod
    def _set_runtime_value(runtime, value, source):
        runtime.value = value
        runtime.valid = True
        runtime.updated_at = time.time()
        runtime.source = source

    def invalidate(self, tag_or_name: TagDefinition | str) -> None:
        if isinstance(tag_or_name, TagDefinition):
            self.invalidate_by_id(self._bind_tag(tag_or_name))
            return
        name = str(tag_or_name)
        tag_ids = self._ids_by_name.get(name, set())
        if len(tag_ids) > 1:
            raise AmbiguousTagNameError(
                f'Tag name "{name}" matches multiple runtime identities.'
            )
        if tag_ids:
            self.invalidate_by_id(next(iter(tag_ids)))
            return
        self._invalidate_runtime(
            self._unbound_values.setdefault(name, TagRuntime())
        )

    @staticmethod
    def _invalidate_runtime(runtime):
        runtime.valid = False
        runtime.updated_at = time.time()

    def _bind_tag(self, tag: TagDefinition) -> str:
        """Register descriptive metadata for an explicit identity operation."""
        tag_id = normalize_tag_id(tag.tag_id)
        previous_name = self._names.get(tag_id)
        if previous_name is not None and previous_name != tag.name:
            previous_ids = self._ids_by_name.get(previous_name, set())
            previous_ids.discard(tag_id)
            if not previous_ids:
                self._ids_by_name.pop(previous_name, None)
        self._names[tag_id] = tag.name
        self._ids_by_name.setdefault(tag.name, set()).add(tag_id)
        self._definitions.setdefault(
            tag_id,
            (
                str(tag.data_type).strip().upper(),
                str(tag.direction).strip(),
                str(tag.address).strip().upper(),
            ),
        )
        self._unbound_values.pop(tag.name, None)
        return tag_id

    def invalidate_all(self) -> None:
        invalidated_at = time.time()
        for runtime in (*self._values.values(), *self._unbound_values.values()):
            runtime.valid = False
            runtime.updated_at = invalidated_at

    def invalidate_source(self, source: RuntimeValueSource) -> None:
        invalidated_at = time.time()
        for runtime in (*self._values.values(), *self._unbound_values.values()):
            if runtime.source == source:
                runtime.valid = False
                runtime.updated_at = invalidated_at

    def clear(self) -> None:
        """Discard all temporary runtime values."""
        self._values.clear()
        self._definitions.clear()
        self._names.clear()
        self._ids_by_name.clear()
        self._unbound_values.clear()

    def get(self, tag_or_name: TagDefinition | str) -> TagRuntime | None:
        if isinstance(tag_or_name, TagDefinition):
            return self.get_by_id(tag_or_name.tag_id)
        return self.get_by_name(str(tag_or_name))

    def get_value(
        self,
        tag_or_name: TagDefinition | str,
        default: Any = None,
    ) -> Any:
        runtime = self.get(tag_or_name)
        if runtime is None or not runtime.valid:
            return default
        return runtime.value

    def snapshot(self) -> dict[str, TagRuntime]:
        return {
            tag_id: TagRuntime(
                item.value,
                item.valid,
                item.updated_at,
                item.source,
            )
            for tag_id, item in self._values.items()
        }

    def restore(
        self,
        snapshot: dict[str, TagRuntime],
        definitions: Iterable[TagDefinition],
    ) -> None:
        """Restore volatile state after a failed configuration transaction."""
        self.sync(definitions)
        for key, item in snapshot.items():
            tag_id = key if key in self._values else self._unique_id_for_name(key)
            if tag_id in self._values:
                self._values[tag_id] = TagRuntime(
                    item.value,
                    item.valid,
                    item.updated_at,
                    item.source,
                )

    def _unique_id_for_name(self, name: str) -> str | None:
        tag_ids = self._ids_by_name.get(str(name), set())
        return next(iter(tag_ids)) if len(tag_ids) == 1 else None
