from core.tag_model import TagDefinition
from core.tag_runtime import RuntimeTagCache, RuntimeValueSource


def test_sync_creates_runtime_entry():
    cache = RuntimeTagCache()
    cache.sync([TagDefinition("Ready", "BOOL", "Input", "DBX0.0")])

    runtime = cache.get("Ready")
    assert runtime is not None
    assert runtime.value is None
    assert runtime.valid is False


def test_update_sets_value_and_good_quality():
    cache = RuntimeTagCache()
    cache.update("Count", 12, RuntimeValueSource.PLC)

    runtime = cache.get("Count")
    assert runtime.value == 12
    assert runtime.valid is True
    assert runtime.source is RuntimeValueSource.PLC
    assert runtime.updated_at is not None


def test_bad_quality_preserves_last_value():
    cache = RuntimeTagCache()
    cache.update("Temperature", 21.5, RuntimeValueSource.PLC)

    cache.invalidate("Temperature")

    runtime = cache.get("Temperature")
    assert runtime.valid is False
    assert runtime.value == 21.5
    assert cache.get_value("Temperature", "BAD") == "BAD"
