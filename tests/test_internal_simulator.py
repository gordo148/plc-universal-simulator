import pytest

from core.tag_model import TagDefinition
from core.tag_runtime import RuntimeTagCache
from drivers.internal_simulator import InternalSimulatorDriver
from services.plc_service import PLCService


@pytest.fixture
def driver():
    simulator = InternalSimulatorDriver()
    assert simulator.connect()
    return simulator


def test_simulator_write_and_read_bool(driver):
    assert driver.read("Motor_Run", "BOOL") is False
    assert driver.write("Motor_Run", True, "BOOL") is True
    assert driver.read("Motor_Run", "BOOL") is True


def test_simulator_write_and_read_int(driver):
    assert driver.read("Batch_Count", "INT") == 0
    assert driver.write("Batch_Count", -42, "INT") == -42
    assert driver.read("Batch_Count", "INT") == -42


def test_simulator_write_and_read_real(driver):
    assert driver.read("Tank_Level", "REAL") == 0.0
    assert driver.write("Tank_Level", 12.5, "REAL") == 12.5
    assert driver.read("Tank_Level", "REAL") == 12.5


def test_simulator_memory_survives_disconnect_and_reconnect(driver):
    driver.write("Setpoint", 25.0, "REAL")
    driver.disconnect()
    assert driver.read("Setpoint", "REAL") is None

    driver.connect()

    assert driver.read("Setpoint", "REAL") == 25.0


def test_plc_service_routes_all_simulator_types_through_runtime_cache():
    cache = RuntimeTagCache()
    service = PLCService(runtime_cache=cache)
    tags = [
        TagDefinition("Run", "BOOL", "Input", "Motor_Run"),
        TagDefinition("Count", "INT", "Input", "Batch_Count"),
        TagDefinition("Level", "REAL", "Input", "Tank_Level"),
    ]

    assert service.connect("Simulator", "")
    assert service.read(tags)
    assert cache.get_value("Run") is False
    assert cache.get_value("Count") == 0
    assert cache.get_value("Level") == 0.0

    assert service.write_bool(tags[0], True) is True
    assert service.write_numeric(tags[1], 7.9) == 7
    assert service.write_numeric(tags[2], 8.25) == 8.25
    assert service.read(tags)

    assert cache.get_value("Run") is True
    assert cache.get_value("Count") == 7
    assert cache.get_value("Level") == 8.25


def test_plc_service_retains_simulator_memory_for_app_session():
    service = PLCService()
    tag = TagDefinition("Count", "INT", "Input", "Batch_Count")
    service.connect("Simulator", "")
    service.write_numeric(tag, 99)

    service.disconnect()
    assert service.connect("Simulator", "")
    assert service.read([tag])

    assert service.runtime_cache.get_value("Count") == 99
