import pytest

from core.tag_model import TagDefinition
from ui.tag_manager import suggest_address, validate_tag_address


@pytest.mark.parametrize(
    ("data_type", "address"),
    [("BOOL", "DBX0.0"), ("INT", "DBW10"), ("REAL", "DBD20")],
)
def test_valid_siemens_addresses(data_type, address):
    assert validate_tag_address("Siemens", data_type, address)[0]


@pytest.mark.parametrize(
    ("data_type", "address"),
    [
        ("BOOL", "DBW0"),
        ("BOOL", "DBX0.8"),
        ("INT", "DBD10"),
        ("INT", "DBW-1"),
        ("REAL", "DBW20"),
        ("REAL", "%MW20"),
    ],
)
def test_invalid_siemens_type_address_combinations(data_type, address):
    assert not validate_tag_address("Siemens", data_type, address)[0]


@pytest.mark.parametrize(
    ("data_type", "address"),
    [("BOOL", "%M0"), ("INT", "%MW10"), ("REAL", "%MW20")],
)
def test_valid_schneider_addresses(data_type, address):
    assert validate_tag_address("Schneider", data_type, address)[0]


@pytest.mark.parametrize(
    ("data_type", "address"),
    [
        ("BOOL", "%MW0"),
        ("INT", "%M10"),
        ("REAL", "%M20"),
        ("REAL", "DBD20"),
        ("REAL", "%MW-1"),
    ],
)
def test_invalid_schneider_type_address_combinations(data_type, address):
    assert not validate_tag_address("Schneider", data_type, address)[0]


@pytest.mark.parametrize(
    ("data_type", "address"),
    [
        ("BOOL", "%M0"),
        ("BOOL", "M0"),
        ("BOOL", "0"),
        ("INT", "%MW0"),
        ("INT", "MW0"),
        ("INT", "0"),
        ("REAL", "%MW0"),
        ("REAL", "MW0"),
        ("REAL", "0"),
    ],
)
def test_valid_generic_modbus_addresses(data_type, address):
    assert validate_tag_address("Modbus TCP", data_type, address)[0]


@pytest.mark.parametrize(
    ("data_type", "address"),
    [
        ("BOOL", "%MW0"),
        ("BOOL", "MW0"),
        ("INT", "%M0"),
        ("INT", "M0"),
        ("REAL", "%M0"),
        ("REAL", "DBD0"),
        ("REAL", "-1"),
        ("REAL", "1.5"),
    ],
)
def test_invalid_generic_modbus_addresses(data_type, address):
    assert not validate_tag_address("Modbus TCP", data_type, address)[0]


def test_generic_modbus_suggestions_account_for_plain_addresses_and_real_size():
    tags = [
        TagDefinition("Coil0", "BOOL", "Input", "0"),
        TagDefinition("Integer0", "INT", "Input", "MW0"),
        TagDefinition("Real1", "REAL", "Input", "%MW1"),
    ]

    assert suggest_address("Modbus TCP", "BOOL", tags) == "%M1"
    assert suggest_address("Modbus TCP", "INT", tags) == "%MW3"
    assert suggest_address("Modbus TCP", "REAL", tags) == "%MW3"
