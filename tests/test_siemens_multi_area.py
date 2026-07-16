from unittest.mock import Mock, call

from snap7.util import set_bool, set_dint, set_int, set_real

from core.tag_model import TagDefinition
from core.tag_runtime import RuntimeTagCache
from services.plc_service import PLCService


def _driver():
    driver = Mock()
    driver.is_connected.return_value = True
    return driver


def test_scan_groups_each_area_and_db_and_decodes_signed_values():
    driver = _driver()

    def read_range(area, db, start, size):
        data = bytearray(size)
        if (area, db) == ("DB", 14):
            set_bool(data, 0, 0, True)
        elif (area, db) == ("DB", 20):
            set_int(data, 0, -12)
        elif area == "M":
            set_dint(data, 0, -123456)
        elif area == "I":
            set_bool(data, 0, 2, True)
        elif area == "Q":
            set_real(data, 0, 1.25)
        return data

    driver.read_range.side_effect = read_range
    cache = RuntimeTagCache()
    service = PLCService(driver, cache)
    tags = [
        TagDefinition("DB14", "BOOL", "Feedback", "%DB14.DBX0.0"),
        TagDefinition("DB20", "INT", "Feedback", "%DB20.DBW4"),
        TagDefinition("Memory", "DINT", "Feedback", "%MD10"),
        TagDefinition("Input", "BOOL", "Feedback", "%I0.2"),
        TagDefinition("Output", "REAL", "Feedback", "%QD20"),
    ]

    assert service.read(tags, brand="Siemens")
    assert {item[:2] for item in [args.args for args in driver.read_range.call_args_list]} == {
        ("DB", 14), ("DB", 20), ("M", None), ("I", None), ("Q", None),
    }
    assert cache.get_value("DB14") is True
    assert cache.get_value("DB20") == -12
    assert cache.get_value("Memory") == -123456
    assert cache.get_value("Input") is True
    assert cache.get_value("Output") == 1.25


def test_writes_receive_parsed_tag_address_and_input_is_blocked():
    driver = _driver()
    driver.write_digital.return_value = True
    driver.write_analog.return_value = -7
    service = PLCService(driver)
    service._brand = "Siemens"

    assert service.write_bool(TagDefinition("Run", "BOOL", "Output", "%Q0.0"), True) is True
    assert service.write_numeric(TagDefinition("Setpoint", "INT", "Output", "%DB20.DBW4"), -7) == -7
    assert service.write_bool(TagDefinition("Sensor", "BOOL", "Input", "%I0.0"), True) is None
    assert driver.write_digital.call_args.args[0].area == "Q"
    assert driver.write_analog.call_args.args[0].db_number == 20


def test_contiguous_tags_share_one_read_but_different_dbs_do_not():
    driver = _driver()
    driver.read_range.side_effect = lambda _area, _db, _start, size: bytearray(size)
    service = PLCService(driver)
    tags = [
        TagDefinition("A", "INT", "Input", "%DB1.DBW0"),
        TagDefinition("B", "REAL", "Input", "%DB1.DBD2"),
        TagDefinition("C", "INT", "Input", "%DB2.DBW0"),
    ]
    assert service.read(tags, brand="Siemens")
    assert driver.read_range.call_args_list == [call("DB", 1, 0, 6), call("DB", 2, 0, 2)]
