import copy

import pytest

from core.tag_model import TagDefinition
from core.tag_runtime import (
    AmbiguousTagNameError,
    DuplicateRuntimeTagIdError,
    RuntimeTagCache,
    RuntimeValueSource,
)


TAG_A_ID = "00000000-0000-4000-8000-000000000001"
TAG_B_ID = "00000000-0000-4000-8000-000000000002"
TAG_C_ID = "00000000-0000-4000-8000-000000000003"


def _tag(name, tag_id, address="M0"):
    return TagDefinition(name, "BOOL", "Input", address, tag_id=tag_id)


def test_runtime_entries_are_keyed_by_stable_id():
    tag = _tag("Ready", TAG_A_ID)
    cache = RuntimeTagCache()
    cache.sync([tag])
    cache.update(tag, True, RuntimeValueSource.PLC)

    assert set(cache.snapshot()) == {TAG_A_ID}
    assert cache.contains_id(TAG_A_ID)
    assert cache.get_by_id(TAG_A_ID).value is True


def test_explicit_tag_update_binds_unique_name_without_prior_sync():
    tag = _tag("Ready", TAG_A_ID)
    cache = RuntimeTagCache()

    cache.update(tag, True)

    assert cache.get("Ready") is cache.get_by_id(TAG_A_ID)


def test_rename_preserves_complete_runtime_state_and_updates_name_lookup():
    tag = _tag("Before", TAG_A_ID)
    cache = RuntimeTagCache()
    cache.sync([tag])
    cache.update_by_id(TAG_A_ID, 42, RuntimeValueSource.PLC)
    before = copy.deepcopy(cache.get_by_id(TAG_A_ID))

    tag.name = "After"
    cache.sync([tag])

    assert cache.get_by_id(TAG_A_ID) == before
    assert cache.get_by_name("After") == before
    assert cache.get_by_name("Before") is None


def test_same_name_with_different_ids_stays_separate_and_is_ambiguous_by_name():
    first = _tag("Shared", TAG_A_ID, "M0")
    second = _tag("Shared", TAG_B_ID, "M1")
    cache = RuntimeTagCache()
    cache.sync([first, second])
    cache.update_by_id(first.tag_id, 1)
    cache.update_by_id(second.tag_id, 2)

    assert cache.get_by_id(first.tag_id).value == 1
    assert cache.get_by_id(second.tag_id).value == 2
    with pytest.raises(AmbiguousTagNameError, match="multiple runtime identities"):
        cache.get("Shared")
    with pytest.raises(AmbiguousTagNameError):
        cache.update("Shared", 3)


def test_duplicate_ids_are_rejected_before_cache_mutation():
    existing = _tag("Existing", TAG_C_ID)
    cache = RuntimeTagCache()
    cache.sync([existing])
    cache.update(existing, True)
    before = cache.snapshot()
    duplicate_a = _tag("First", TAG_A_ID)
    duplicate_b = _tag("Second", TAG_A_ID)

    with pytest.raises(DuplicateRuntimeTagIdError, match="Duplicate runtime tag_id"):
        cache.sync([duplicate_a, duplicate_b])

    assert cache.snapshot() == before
    assert cache.get("Existing").value is True


def test_reordering_does_not_change_runtime_state():
    first = _tag("First", TAG_A_ID)
    second = _tag("Second", TAG_B_ID)
    cache = RuntimeTagCache()
    cache.sync([first, second])
    cache.update(first, 1)
    cache.update(second, 2)
    before = cache.snapshot()

    cache.sync([second, first])

    assert cache.snapshot() == before


def test_replacement_with_reused_name_does_not_inherit_runtime_state():
    original = _tag("Motor", TAG_A_ID)
    replacement = _tag("Motor", TAG_B_ID)
    cache = RuntimeTagCache()
    cache.sync([original])
    cache.update(original, True)

    cache.sync([replacement])

    assert cache.contains_id(original.tag_id) is False
    assert cache.get(replacement).valid is False
    assert cache.get(replacement).value is None


def test_reused_address_with_different_id_does_not_inherit_state():
    original = _tag("Old", TAG_A_ID, "M10")
    replacement = _tag("New", TAG_B_ID, "M10")
    cache = RuntimeTagCache()
    cache.sync([original])
    cache.update(original, True)

    cache.sync([replacement])

    assert cache.get(replacement).value is None


def test_existing_signature_change_keeps_identity_but_resets_state():
    tag = _tag("Motor", TAG_A_ID, "M0")
    cache = RuntimeTagCache()
    cache.sync([tag])
    cache.update(tag, True)

    tag.address = "M1"
    cache.sync([tag])

    assert cache.contains_id(TAG_A_ID)
    assert cache.get(tag).valid is False
    assert cache.get(tag).value is None


def test_snapshot_restores_by_identity_after_rename():
    tag = _tag("Before", TAG_A_ID)
    cache = RuntimeTagCache()
    cache.sync([tag])
    cache.update(tag, 7, RuntimeValueSource.PLC)
    snapshot = cache.snapshot()

    tag.name = "After"
    cache.clear()
    cache.restore(snapshot, [tag])

    assert cache.get("After").value == 7
    assert cache.get("After").source is RuntimeValueSource.PLC
    assert cache.get("Before") is None


def test_snapshot_does_not_restore_state_to_replacement_with_same_name():
    original = _tag("Motor", TAG_A_ID)
    replacement = _tag("Motor", TAG_B_ID)
    cache = RuntimeTagCache()
    cache.sync([original])
    cache.update(original, True)
    snapshot = cache.snapshot()

    cache.restore(snapshot, [replacement])

    assert cache.get(replacement).value is None
    assert cache.get(replacement).valid is False


def test_legacy_name_snapshot_adapter_requires_a_unique_current_name():
    tag = _tag("Motor", TAG_A_ID)
    source = RuntimeTagCache()
    source.update("Motor", True, RuntimeValueSource.SIMULATION)
    legacy_snapshot = {"Motor": copy.deepcopy(source.get("Motor"))}
    cache = RuntimeTagCache()

    cache.restore(legacy_snapshot, [tag])

    assert cache.get(tag).value is True


def test_unbound_name_state_is_not_transferred_during_sync():
    tag = _tag("Motor", TAG_A_ID)
    cache = RuntimeTagCache()
    cache.update("Motor", True)

    cache.sync([tag])

    assert cache.get(tag).value is None
    assert cache.get(tag).valid is False


def test_id_invalidation_affects_only_selected_duplicate_name_tag():
    first = _tag("Shared", TAG_A_ID)
    second = _tag("Shared", TAG_B_ID)
    cache = RuntimeTagCache()
    cache.sync([first, second])
    cache.update_by_id(first.tag_id, 1)
    cache.update_by_id(second.tag_id, 2)

    cache.invalidate_by_id(first.tag_id)

    assert cache.get_by_id(first.tag_id).valid is False
    assert cache.get_by_id(second.tag_id).valid is True


def test_clear_removes_all_identities_and_compatibility_values():
    tag = _tag("Bound", TAG_A_ID)
    cache = RuntimeTagCache()
    cache.sync([tag])
    cache.update(tag, True)
    cache.update("Unbound", 1)

    cache.clear()

    assert cache.snapshot() == {}
    assert cache.contains_id(TAG_A_ID) is False
    assert cache.get("Unbound") is None
