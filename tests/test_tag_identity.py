import copy
import uuid

import pytest

from core.tag_identity import (
    InvalidTagIdError,
    generate_tag_id,
    is_valid_tag_id,
    normalize_tag_id,
)
from core.tag_model import Tag, TagDefinition


def test_generated_tag_id_is_canonical_uuid_v4():
    generated = generate_tag_id()
    parsed = uuid.UUID(generated)

    assert parsed.version == 4
    assert parsed.variant == uuid.RFC_4122
    assert generated == str(parsed)
    assert generated == generated.lower()
    assert len(generated.split("-")) == 5


def test_generated_tag_ids_are_unique_across_reasonable_sample():
    generated = {generate_tag_id() for _ in range(256)}

    assert len(generated) == 256
    assert all(is_valid_tag_id(value) for value in generated)


def test_normalize_tag_id_accepts_uppercase_and_uuid_objects():
    value = uuid.uuid4()

    assert normalize_tag_id(str(value).upper()) == str(value)
    assert normalize_tag_id(value) == str(value)


@pytest.mark.parametrize(
    "value",
    [None, "", "not-a-uuid", "1234", uuid.uuid1()],
    ids=["none", "empty", "malformed", "short", "not-v4"],
)
def test_invalid_tag_ids_are_rejected(value):
    with pytest.raises(InvalidTagIdError, match="UUID v4"):
        normalize_tag_id(value)

    assert is_valid_tag_id(value) is False


def test_is_valid_tag_id_accepts_valid_uuid_v4():
    assert is_valid_tag_id(uuid.uuid4()) is True


def test_old_positional_constructor_order_is_unchanged():
    tag = TagDefinition(
        "Motor",
        "BOOL",
        "Input",
        "%M0.0",
        True,
        True,
        False,
        True,
        "Main motor",
    )

    assert (
        tag.name,
        tag.data_type,
        tag.direction,
        tag.address,
        tag.enabled_sim,
        tag.enabled_trend,
        tag.enabled_alarm,
        tag.enabled_dashboard,
        tag.comment,
    ) == (
        "Motor",
        "BOOL",
        "Input",
        "%M0.0",
        True,
        True,
        False,
        True,
        "Main motor",
    )
    assert is_valid_tag_id(tag.tag_id)


def test_keyword_constructor_and_compatibility_alias_generate_identity():
    tag = Tag(
        name="Level",
        data_type="REAL",
        direction="Input",
        address="%MW10",
        enabled_dashboard=True,
        comment="Tank level",
    )

    assert isinstance(tag, TagDefinition)
    assert tag.enabled_dashboard is True
    assert tag.comment == "Tank level"
    assert is_valid_tag_id(tag.tag_id)


def test_two_new_tags_receive_different_ids():
    first = TagDefinition("A", "BOOL", "Input", "M0")
    second = TagDefinition("B", "BOOL", "Input", "M1")

    assert first.tag_id != second.tag_id


def test_explicit_valid_id_is_normalized_and_preserved():
    explicit = uuid.uuid4()
    tag = TagDefinition("A", "BOOL", "Input", "M0", tag_id=str(explicit).upper())

    assert tag.tag_id == str(explicit)


@pytest.mark.parametrize("value", [None, "", "bad-id", uuid.uuid1()])
def test_tag_definition_rejects_invalid_explicit_id(value):
    with pytest.raises(InvalidTagIdError):
        TagDefinition("A", "BOOL", "Input", "M0", tag_id=value)


def test_engineering_field_edits_preserve_tag_id():
    tag = TagDefinition("A", "BOOL", "Input", "M0")
    original_id = tag.tag_id

    tag.name = "Renamed"
    assert tag.tag_id == original_id
    tag.address = "M10"
    assert tag.tag_id == original_id
    tag.data_type = "INT"
    assert tag.tag_id == original_id
    tag.direction = "Output"
    assert tag.tag_id == original_id
    tag.enabled_sim = True
    tag.enabled_trend = True
    tag.enabled_alarm = True
    tag.enabled_dashboard = True
    assert tag.tag_id == original_id


def test_deepcopy_preserves_tag_id_for_snapshot_and_rollback():
    tag = TagDefinition("A", "BOOL", "Input", "M0")

    copied = copy.deepcopy(tag)

    assert copied is not tag
    assert copied.tag_id == tag.tag_id


def test_structural_dataclass_equality_remains_backward_compatible():
    first = TagDefinition("A", "BOOL", "Input", "M0")
    second = TagDefinition("A", "BOOL", "Input", "M0")

    assert first.tag_id != second.tag_id
    assert first == second


def test_project_dictionary_includes_stable_identity():
    tag = TagDefinition("A", "BOOL", "Input", "M0", comment="Comment")

    serialized = tag.to_dict()

    assert serialized == {
        "tag_id": tag.tag_id,
        "name": "A",
        "data_type": "BOOL",
        "direction": "Input",
        "address": "M0",
        "enabled_sim": False,
        "enabled_trend": False,
        "enabled_alarm": False,
        "enabled_dashboard": False,
        "comment": "Comment",
    }


def test_project_dictionary_identity_round_trips():
    tag = TagDefinition("A", "BOOL", "Input", "M0")

    restored = TagDefinition.from_dict(tag.to_dict())

    assert restored.tag_id == tag.tag_id


def test_legacy_project_dictionary_creates_new_in_memory_identity():
    tag = TagDefinition.from_dict(
        {
            "name": "Legacy",
            "data_type": "BOOL",
            "direction": "Input",
            "address": "M0",
        }
    )

    assert tag.name == "Legacy"
    assert is_valid_tag_id(tag.tag_id)


def test_project_dictionary_rejects_malformed_explicit_identity():
    with pytest.raises(InvalidTagIdError):
        TagDefinition.from_dict(
            {
                "tag_id": "not-a-uuid",
                "name": "Broken",
                "data_type": "BOOL",
                "direction": "Input",
                "address": "M0",
            }
        )
