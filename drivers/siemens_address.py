"""Canonical parsing and type validation for absolute Siemens addresses."""

from __future__ import annotations

from dataclasses import dataclass
import re


_DB_RE = re.compile(r"DB(\d+)\.(DB[XBWD])(\d+)(?:\.(\d+))?", re.IGNORECASE)
_AREA_RE = re.compile(r"([MIEQA])([BWD]?)(\d+)(?:\.(\d+))?", re.IGNORECASE)
_WIDTHS = {"X": 1, "B": 8, "W": 16, "D": 32}
_TYPE_WIDTHS = {
    "BOOL": 1,
    "BYTE": 8,
    "WORD": 16,
    "INT": 16,
    "DWORD": 32,
    "DINT": 32,
    "REAL": 32,
}


class SiemensAddressError(ValueError):
    """Raised when a Siemens address is empty, malformed, or incompatible."""


@dataclass(frozen=True)
class SiemensAddress:
    normalized_address: str
    area: str
    db_number: int | None
    unit: str
    byte_offset: int
    bit_offset: int | None
    width_bits: int

    @property
    def size_bytes(self) -> int:
        return max(1, self.width_bits // 8)

    def to_dict(self) -> dict:
        return {
            "normalized_address": self.normalized_address,
            "area": self.area,
            "db_number": self.db_number,
            "unit": self.unit,
            "byte_offset": self.byte_offset,
            "bit_offset": self.bit_offset,
            "width_bits": self.width_bits,
        }


def parse_siemens_address(address: str) -> SiemensAddress:
    raw = str(address or "").strip()
    if not raw:
        raise SiemensAddressError("Siemens address is empty.")
    value = raw.upper().removeprefix("%")

    match = _DB_RE.fullmatch(value)
    if match:
        db_number = int(match.group(1))
        if db_number <= 0:
            raise SiemensAddressError("DB number must be greater than zero.")
        unit = match.group(2).upper()
        byte_offset = int(match.group(3))
        bit_offset = _validated_bit(unit, match.group(4))
        suffix = f"{byte_offset}.{bit_offset}" if unit == "DBX" else str(byte_offset)
        return SiemensAddress(
            f"%DB{db_number}.{unit}{suffix}", "DB", db_number, unit,
            byte_offset, bit_offset, _WIDTHS[unit[-1]],
        )

    match = _AREA_RE.fullmatch(value)
    if match:
        area = {"E": "I", "A": "Q"}.get(match.group(1).upper(), match.group(1).upper())
        qualifier = match.group(2).upper()
        byte_offset = int(match.group(3))
        bit_text = match.group(4)
        if bit_text is not None:
            if qualifier:
                raise SiemensAddressError("Bit addresses must use AREAbyte.bit syntax.")
            bit_offset = _validated_bit("X", bit_text)
            unit = area
            normalized = f"%{area}{byte_offset}.{bit_offset}"
            width = 1
        else:
            if not qualifier:
                raise SiemensAddressError("Incomplete Siemens address; a bit or B/W/D unit is required.")
            bit_offset = None
            unit = f"{area}{qualifier}"
            normalized = f"%{unit}{byte_offset}"
            width = _WIDTHS[qualifier]
        return SiemensAddress(normalized, area, None, unit, byte_offset, bit_offset, width)

    raise SiemensAddressError(
        f"Invalid Siemens address syntax: {raw}. Expected DBx.DBXbyte.bit, DBB/DBW/DBD, or M/I/Q byte addressing."
    )


def _validated_bit(unit: str, bit_text: str | None) -> int | None:
    is_bit = unit in ("X", "DBX")
    if is_bit and bit_text is None:
        raise SiemensAddressError("Bit address is incomplete; expected a bit from 0 to 7.")
    if not is_bit and bit_text is not None:
        raise SiemensAddressError(f"{unit} does not accept a bit offset.")
    if bit_text is None:
        return None
    bit = int(bit_text)
    if not 0 <= bit <= 7:
        raise SiemensAddressError(f"Bit offset must be between 0 and 7; received {bit}.")
    return bit


def validate_siemens_data_type(data_type: str, address: str | SiemensAddress) -> SiemensAddress:
    parsed = address if isinstance(address, SiemensAddress) else parse_siemens_address(address)
    normalized_type = str(data_type or "").strip().upper()
    expected_width = _TYPE_WIDTHS.get(normalized_type)
    if expected_width is None:
        raise SiemensAddressError(f"Unsupported Siemens data type: {data_type}.")
    if parsed.width_bits != expected_width:
        if normalized_type == "BOOL":
            requirement = "a bit address"
        else:
            examples = {8: "DBB, MB, IB or QB", 16: "DBW, MW, IW or QW", 32: "DBD, MD, ID or QD"}
            requirement = f"a {expected_width}-bit address such as {examples[expected_width]}"
        raise SiemensAddressError(
            f"{normalized_type} requires {requirement}. Received address: {parsed.normalized_address}"
        )
    return parsed


def normalize_siemens_address(address: str) -> str:
    return parse_siemens_address(address).normalized_address
