import pytest

from drivers.siemens_address import (
    SiemensAddressError, parse_siemens_address, validate_siemens_data_type,
)


@pytest.mark.parametrize("address", [
    "%DB14.DBX0.0", "DB14.DBX0.7", "%DB14.DBB2", "%DB14.DBW4", "%DB14.DBD8",
    "%M10.0", "%MB10", "%MW10", "%MD10", "%I0.0", "%IB10", "%IW10", "%ID10",
    "%Q0.0", "%QB10", "%QW10", "%QD10", "%E0.0", "%EW10", "%A0.0", "%AW10",
])
def test_valid_addresses(address):
    assert parse_siemens_address(address).normalized_address.startswith("%")


@pytest.mark.parametrize(("address", "normalized"), [
    ("db14.dbx0.0", "%DB14.DBX0.0"), ("e0.0", "%I0.0"), ("aw10", "%QW10"),
])
def test_normalization(address, normalized):
    assert parse_siemens_address(address).normalized_address == normalized


@pytest.mark.parametrize("address", [
    "%DB.DBX0.0", "%DB14.DBX0.8", "%DB14.DBW-1", "%M10.9", "%DB14", "%XYZ10", "texto", "",
])
def test_invalid_addresses(address):
    with pytest.raises(SiemensAddressError):
        parse_siemens_address(address)


@pytest.mark.parametrize(("data_type", "address"), [
    ("BOOL", "%DB1.DBX0.0"), ("BOOL", "%M0.0"), ("INT", "%DB1.DBW0"), ("REAL", "%DB1.DBD0"),
    ("BYTE", "%MB0"), ("WORD", "%QW0"), ("DWORD", "%MD0"), ("DINT", "%ID0"),
])
def test_compatible_types(data_type, address):
    assert validate_siemens_data_type(data_type, address)


@pytest.mark.parametrize(("data_type", "address"), [
    ("REAL", "%DB1.DBW0"), ("BOOL", "%MW10"), ("INT", "%M0.0"),
])
def test_incompatible_types(data_type, address):
    with pytest.raises(SiemensAddressError):
        validate_siemens_data_type(data_type, address)
