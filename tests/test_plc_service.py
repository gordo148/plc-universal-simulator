from unittest.mock import Mock

from snap7.util import set_bool, set_int, set_real

from core.tag_model import TagDefinition
from core.tag_runtime import RuntimeTagCache
from services.plc_service import PLCService
from services import plc_service


def connected_driver():
    driver = Mock()
    driver.is_connected.return_value = True
    return driver


def test_generic_modbus_connect_uses_generic_driver(monkeypatch):
    driver = Mock()
    driver.connect.return_value = True
    driver.is_connected.return_value = True
    driver_type = Mock(return_value=driver)
    monkeypatch.setattr(plc_service, "ModbusTCPDriver", driver_type)
    service = PLCService()

    assert service.connect(
        "Modbus TCP",
        "192.0.2.10",
        port="1502",
        slave_id="7",
    )

    driver_type.assert_called_once_with()
    driver.connect.assert_called_once_with("192.0.2.10", 1502, 7)
    assert service._brand == "Modbus TCP"


def test_siemens_read_routes_to_driver_and_decodes_values():
    driver = connected_driver()
    data = bytearray(24)
    set_bool(data, 0, 0, True)
    set_int(data, 10, -123)
    set_real(data, 20, 12.5)
    driver.read_data.return_value = data
    cache = RuntimeTagCache()
    service = PLCService(driver, cache)
    tags = [
        TagDefinition("Run", "BOOL", "Input", "DBX0.0"),
        TagDefinition("Count", "INT", "Input", "DBW10"),
        TagDefinition("Level", "REAL", "Input", "DBD20"),
    ]

    assert service.read(tags, brand="Siemens")

    driver.read_data.assert_called_once_with(24)
    assert cache.get_value("Run") is True
    assert cache.get_value("Count") == -123
    assert cache.get_value("Level") == 12.5


def test_schneider_read_routes_bool_int_and_real_to_mock_driver():
    driver = connected_driver()
    driver.read_coils_block.return_value = [True]
    driver.read_registers_block.return_value = [42, 0x4148, 0x0000]
    cache = RuntimeTagCache()
    service = PLCService(driver, cache)
    tags = [
        TagDefinition("Run", "BOOL", "Input", "%M0"),
        TagDefinition("Count", "INT", "Input", "%MW10"),
        TagDefinition("Level", "REAL", "Input", "%MW11"),
    ]

    assert service.read(tags, brand="Schneider")

    driver.read_coils_block.assert_called_once_with(0, 1)
    driver.read_registers_block.assert_called_once_with(10, 3)
    assert cache.get_value("Run") is True
    assert cache.get_value("Count") == 42
    assert cache.get_value("Level") == 12.5


def test_siemens_writes_route_by_tag_type():
    driver = connected_driver()
    driver.write_digital.return_value = True
    driver.write_analog.return_value = 77
    service = PLCService(driver)
    service._brand = "Siemens"
    bool_tag = TagDefinition("Run", "BOOL", "Output", "DBX2.3")
    int_tag = TagDefinition("Speed", "INT", "Output", "DBW10")

    assert service.write_bool(bool_tag, True) is True
    assert service.write_numeric(int_tag, 77) == 77

    driver.write_digital.assert_called_once_with(2, 3, True)
    driver.write_analog.assert_called_once_with(10, 77, "INT")


def test_schneider_writes_route_by_tag_type():
    driver = connected_driver()
    driver.write_digital.return_value = False
    driver.write_analog.return_value = 3.5
    service = PLCService(driver)
    service._brand = "Schneider"
    bool_tag = TagDefinition("Run", "BOOL", "Output", "%M5")
    real_tag = TagDefinition("Speed", "REAL", "Output", "%MW20")

    assert service.write_bool(bool_tag, False) is False
    assert service.write_numeric(real_tag, 3.5) == 3.5

    driver.write_digital.assert_called_once_with(5, False)
    driver.write_analog.assert_called_once_with(20, 3.5, "REAL")


def test_generic_modbus_read_routes_all_address_forms_to_mock_driver():
    driver = connected_driver()
    driver.read_coils_block.return_value = [True]
    driver.read_registers_block.return_value = [42, 0x4148, 0x0000]
    cache = RuntimeTagCache()
    service = PLCService(driver, cache)
    tags = [
        TagDefinition("Run", "BOOL", "Input", "M0"),
        TagDefinition("Count", "INT", "Input", "10"),
        TagDefinition("Level", "REAL", "Input", "%MW11"),
    ]

    assert service.read(tags, brand="Modbus TCP")

    driver.read_coils_block.assert_called_once_with(0, 1)
    driver.read_registers_block.assert_called_once_with(10, 3)
    assert cache.get_value("Run") is True
    assert cache.get_value("Count") == 42
    assert cache.get_value("Level") == 12.5


def test_generic_modbus_writes_route_coils_and_holding_registers():
    driver = connected_driver()
    driver.write_digital.return_value = True
    driver.write_analog.side_effect = [17, 3.5]
    service = PLCService(driver)
    service._brand = "Modbus TCP"
    bool_tag = TagDefinition("Run", "BOOL", "Output", "5")
    int_tag = TagDefinition("Count", "INT", "Output", "MW10")
    real_tag = TagDefinition("Speed", "REAL", "Output", "%MW20")

    assert service.write_bool(bool_tag, True) is True
    assert service.write_numeric(int_tag, 17) == 17
    assert service.write_numeric(real_tag, 3.5) == 3.5

    driver.write_digital.assert_called_once_with(5, True)
    assert driver.write_analog.call_args_list == [
        ((10, 17, "INT"), {}),
        ((20, 3.5, "REAL"), {}),
    ]


def test_generic_modbus_offline_read_never_calls_driver():
    driver = Mock()
    driver.is_connected.return_value = False
    cache = RuntimeTagCache()
    service = PLCService(driver, cache)
    tag = TagDefinition("Run", "BOOL", "Input", "0")

    assert service.read([tag], brand="Modbus TCP") is False
    assert cache.get("Run").valid is False
    driver.read_coils_block.assert_not_called()


def test_rockwell_connect_uses_ip_only_driver(monkeypatch):
    driver = Mock()
    driver.connect.return_value = True
    driver_type = Mock(return_value=driver)
    monkeypatch.setattr(plc_service, "RockwellEtherNetIPDriver", driver_type)
    service = PLCService()

    assert service.connect("Rockwell", "192.0.2.20")

    driver_type.assert_called_once_with()
    driver.connect.assert_called_once_with("192.0.2.20")
    assert service._brand == "Rockwell"


def test_rockwell_read_routes_symbolic_tags_and_updates_runtime_cache():
    driver = connected_driver()
    driver.read_tags.return_value = {
        "Start_Button": True,
        "Batch_Count": 12,
        "Tank_Level": 8.1254,
    }
    cache = RuntimeTagCache()
    service = PLCService(driver, cache)
    tags = [
        TagDefinition("Start", "BOOL", "Input", "Start_Button"),
        TagDefinition("Count", "INT", "Input", "Batch_Count"),
        TagDefinition("Level", "REAL", "Input", "Tank_Level"),
    ]

    assert service.read(tags, brand="Rockwell")

    driver.read_tags.assert_called_once_with(
        ["Start_Button", "Batch_Count", "Tank_Level"]
    )
    assert cache.get_value("Start") is True
    assert cache.get_value("Count") == 12
    assert cache.get_value("Level") == 8.125


def test_rockwell_writes_route_symbolic_bool_int_and_real_values():
    driver = connected_driver()
    driver.write_tag.side_effect = [True, 21, 4.5]
    service = PLCService(driver)
    service._brand = "Rockwell"
    bool_tag = TagDefinition("Start", "BOOL", "Output", "Start_Button")
    int_tag = TagDefinition("Count", "INT", "Output", "Batch_Count")
    real_tag = TagDefinition("Output", "REAL", "Output", "PID_OUT")

    assert service.write_bool(bool_tag, True) is True
    assert service.write_numeric(int_tag, 21.9) == 21
    assert service.write_numeric(real_tag, 4.5) == 4.5

    assert driver.write_tag.call_args_list == [
        (("Start_Button", True), {}),
        (("Batch_Count", 21), {}),
        (("PID_OUT", 4.5), {}),
    ]


def test_rockwell_failed_read_marks_quality_bad_and_preserves_last_value():
    driver = connected_driver()
    driver.read_tags.side_effect = [
        {"Tank_Level": 10.0},
        {},
    ]
    cache = RuntimeTagCache()
    service = PLCService(driver, cache)
    tag = TagDefinition("Level", "REAL", "Input", "Tank_Level")

    assert service.read([tag], brand="Rockwell")
    assert service.read([tag], brand="Rockwell") is False

    runtime = cache.get("Level")
    assert runtime.valid is False
    assert runtime.value == 10.0


def test_rockwell_offline_read_does_not_call_driver():
    driver = Mock()
    driver.is_connected.return_value = False
    cache = RuntimeTagCache()
    service = PLCService(driver, cache)
    tag = TagDefinition("Start", "BOOL", "Input", "Start_Button")

    assert service.read([tag], brand="Rockwell") is False
    assert cache.get("Start").valid is False
    driver.read_tags.assert_not_called()
