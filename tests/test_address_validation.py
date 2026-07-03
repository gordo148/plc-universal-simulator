import pytest

from ui.tag_manager import validate_tag_address


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
