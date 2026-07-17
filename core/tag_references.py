from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from core.tag_identity import InvalidTagIdError, normalize_tag_id


class TagReferenceError(ValueError):
    """Base error for an invalid, unresolved or ambiguous tag reference."""


class InvalidTagReferenceError(TagReferenceError):
    pass


class UnresolvedTagReferenceError(TagReferenceError):
    pass


class AmbiguousTagReferenceError(TagReferenceError):
    pass


@dataclass(frozen=True)
class TagReferenceIndex:
    by_id: dict[str, Any]
    by_name: dict[str, tuple[Any, ...]]


def _value(tag, field, default=""):
    if isinstance(tag, Mapping):
        return tag.get(field, default)
    return getattr(tag, field, default)


def build_tag_reference_index(tags: Iterable[Any]) -> TagReferenceIndex:
    by_id = {}
    by_name: dict[str, list[Any]] = {}
    for tag in tags:
        try:
            tag_id = normalize_tag_id(_value(tag, "tag_id"))
        except InvalidTagIdError as error:
            raise InvalidTagReferenceError(f"Tag index contains an invalid ID: {error}") from error
        if tag_id in by_id:
            raise InvalidTagReferenceError(f'Duplicate tag_id "{tag_id}" in reference index.')
        by_id[tag_id] = tag
        by_name.setdefault(str(_value(tag, "name")), []).append(tag)
    return TagReferenceIndex(by_id, {name: tuple(items) for name, items in by_name.items()})


def resolve_tag_reference(
    reference: Any,
    index: TagReferenceIndex,
    *,
    context: str,
):
    tag_id = None
    tag_name = None
    if isinstance(reference, Mapping):
        tag_id = reference.get("tag_id")
        tag_name = reference.get("tag_name") or reference.get("name")
    elif reference is not None:
        tag_name = str(reference)

    if tag_id is not None:
        try:
            normalized = normalize_tag_id(tag_id)
        except InvalidTagIdError as error:
            raise InvalidTagReferenceError(f"{context}: invalid tag ID: {error}") from error
        tag = index.by_id.get(normalized)
        if tag is None:
            raise UnresolvedTagReferenceError(
                f'{context}: tag ID "{normalized}" does not exist in this project.'
            )
        return tag

    name = str(tag_name or "").strip()
    matches = index.by_name.get(name, ())
    if not matches:
        raise UnresolvedTagReferenceError(
            f'{context}: legacy tag name "{name}" could not be resolved.'
        )
    if len(matches) > 1:
        raise AmbiguousTagReferenceError(
            f'{context}: legacy tag name "{name}" is ambiguous.'
        )
    return matches[0]


def serialize_tag_reference(tag: Any) -> dict[str, str]:
    try:
        tag_id = normalize_tag_id(_value(tag, "tag_id"))
    except InvalidTagIdError as error:
        raise InvalidTagReferenceError(f"Cannot serialize tag reference: {error}") from error
    return {"tag_id": tag_id, "tag_name": str(_value(tag, "name"))}
