from types import SimpleNamespace
from unittest.mock import Mock

from drivers import rockwell_enip


def response(tag, value, error=None):
    return SimpleNamespace(tag=tag, value=value, error=error)


def test_rockwell_driver_wraps_pycomm3_read_and_write(monkeypatch):
    client = Mock()
    client.open.return_value = True
    client.connected = True
    client.read.return_value = [
        response("Start_Button", True),
        response("Tank_Level", 12.5),
    ]
    client.write.return_value = response("PID_OUT", 7.5)
    logix_driver = Mock(return_value=client)
    monkeypatch.setattr(rockwell_enip, "LogixDriver", logix_driver)
    driver = rockwell_enip.RockwellEtherNetIPDriver()

    assert driver.connect("192.0.2.20")
    assert driver.read_tags(["Start_Button", "Tank_Level"]) == {
        "Start_Button": True,
        "Tank_Level": 12.5,
    }
    assert driver.write_tag("PID_OUT", 7.5) == 7.5

    logix_driver.assert_called_once_with("192.0.2.20")
    client.read.assert_called_once_with("Start_Button", "Tank_Level")
    client.write.assert_called_once_with(("PID_OUT", 7.5))


def test_rockwell_driver_omits_failed_read_results(monkeypatch):
    client = Mock()
    client.open.return_value = True
    client.connected = True
    client.read.return_value = response("Missing_Tag", None, "not found")
    monkeypatch.setattr(rockwell_enip, "LogixDriver", Mock(return_value=client))
    driver = rockwell_enip.RockwellEtherNetIPDriver()
    driver.connect("192.0.2.20")

    assert driver.read_tags(["Missing_Tag"]) == {}
