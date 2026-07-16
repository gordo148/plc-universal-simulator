"""Siemens S7 transport using absolute per-tag PLC areas."""

import snap7
from snap7.type import Areas
from snap7.util import (
    get_bool, get_byte, get_dint, get_dword, get_int, get_real, get_word,
    set_bool, set_byte, set_dint, set_dword, set_int, set_real, set_word,
)

from drivers.siemens_address import SiemensAddress, validate_siemens_data_type


_AREAS = {"DB": Areas.DB, "M": Areas.MK, "I": Areas.PE, "Q": Areas.PA}


class SiemensS7Driver:
    def __init__(self):
        self.client = snap7.client.Client()

    def connect(self, ip, rack=0, slot=1):
        self.client.connect(ip, int(rack), int(slot))
        return self.client.get_connected()

    def disconnect(self):
        self.client.disconnect()

    def is_connected(self):
        return self.client.get_connected()

    def read_range(self, area, db_number, start, size):
        if not self.is_connected():
            return None
        return self.client.read_area(
            _AREAS[area], int(db_number or 0), int(start), int(size)
        )

    def write_digital(self, address: SiemensAddress | str, value):
        parsed = validate_siemens_data_type("BOOL", address)
        self._ensure_writable(parsed)
        data = bytearray(self.read_range(parsed.area, parsed.db_number, parsed.byte_offset, 1) or b"")
        if len(data) != 1:
            return None
        set_bool(data, 0, parsed.bit_offset, bool(value))
        self._write_range(parsed, data)
        verified = self.read_range(parsed.area, parsed.db_number, parsed.byte_offset, 1)
        return None if verified is None or len(verified) != 1 else get_bool(verified, 0, parsed.bit_offset)

    def write_analog(self, address: SiemensAddress | str, value, data_type="INT"):
        parsed = validate_siemens_data_type(data_type, address)
        self._ensure_writable(parsed)
        data_type = str(data_type).strip().upper()
        data = bytearray(parsed.size_bytes)
        setters = {
            "BYTE": lambda: set_byte(data, 0, int(value)),
            "WORD": lambda: set_word(data, 0, int(value)),
            "INT": lambda: set_int(data, 0, int(value)),
            "DWORD": lambda: set_dword(data, 0, int(value)),
            "DINT": lambda: set_dint(data, 0, int(value)),
            "REAL": lambda: set_real(data, 0, float(value)),
        }
        setters[data_type]()
        self._write_range(parsed, data)
        verified = self.read_range(parsed.area, parsed.db_number, parsed.byte_offset, parsed.size_bytes)
        if verified is None or len(verified) != parsed.size_bytes:
            return None
        getters = {
            "BYTE": get_byte, "WORD": get_word, "INT": get_int,
            "DWORD": get_dword, "DINT": get_dint, "REAL": get_real,
        }
        return getters[data_type](verified, 0)

    def _write_range(self, address: SiemensAddress, data):
        if not self.is_connected():
            return None
        return self.client.write_area(
            _AREAS[address.area], int(address.db_number or 0),
            int(address.byte_offset), data,
        )

    @staticmethod
    def _ensure_writable(address: SiemensAddress):
        if address.area == "I":
            raise PermissionError(
                f"Cannot write {address.normalized_address} because the input area is read-only."
            )
