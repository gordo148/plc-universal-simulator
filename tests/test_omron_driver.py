from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from drivers import omron_fins


def response(data=b"", ok=True):
    return SimpleNamespace(data=data, ok=ok)


def connected_driver(monkeypatch):
    client = Mock()
    client_type = Mock(return_value=client)
    monkeypatch.setattr(omron_fins, "FinsClient", client_type)
    driver = omron_fins.OmronFINSDriver()
    assert driver.connect("192.0.2.30", 9600, 10, 20)
    return driver, client, client_type


def test_missing_fins_dependency_fails_only_when_omron_connects(monkeypatch):
    monkeypatch.setattr(omron_fins, "FinsClient", None)
    driver = omron_fins.OmronFINSDriver()

    with pytest.raises(RuntimeError, match="pip install fins-driver"):
        driver.connect("192.0.2.30")

    assert driver.is_connected() is False


def test_omron_driver_connects_with_fins_nodes(monkeypatch):
    driver, client, client_type = connected_driver(monkeypatch)

    client_type.assert_called_once_with(
        host="192.0.2.30",
        port=9600,
        mode="udp",
    )
    assert client.da1 == 10
    assert client.sa1 == 20
    client.connect.assert_called_once_with()
    assert driver.is_connected()


def test_omron_driver_reads_bool_int_and_real(monkeypatch):
    driver, client, _ = connected_driver(monkeypatch)
    client.memory_area_read.side_effect = [
        response(b"\x01"),
        response(b"\xff\x85"),
        response(b"\x00\x00\x41\x48"),
    ]

    assert driver.read_bool("CIO0.00") is True
    assert driver.read_int("D100") == -123
    assert driver.read_real("D300") == pytest.approx(12.5)

    assert client.memory_area_read.call_args_list == [
        (("CIO0.00",), {"num_items": 1}),
        (("D100",), {"num_items": 1}),
        (("D300",), {"num_items": 2}),
    ]


def test_omron_driver_writes_bool_int_and_real(monkeypatch):
    driver, client, _ = connected_driver(monkeypatch)
    client.memory_area_write.return_value = response()

    assert driver.write_bool("CIO100.05", True) is True
    assert driver.write_int("D200", -123) == -123
    assert driver.write_real("D300", 12.5) == pytest.approx(12.5)

    assert client.memory_area_write.call_args_list == [
        (("CIO100.05", b"\x01"), {"num_items": 1}),
        (("D200", b"\xff\x85"), {"num_items": 1}),
        (("D300", b"\x00\x00\x41\x48"), {"num_items": 2}),
    ]
