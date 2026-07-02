"""Centralized PLC polling and runtime tag decoding."""

import struct
from typing import Any, Iterable

from snap7.util import get_bool, get_int, get_real

from core.tag_model import TagDefinition
from core.tag_runtime import RuntimeTagCache, RuntimeValueSource
from drivers.schneider_modbus import SchneiderModbusDriver
from drivers.siemens_s7 import SiemensS7Driver


class PLCService:
    def __init__(
        self,
        driver: Any | None = None,
        runtime_cache: RuntimeTagCache | None = None,
    ) -> None:
        self._driver = driver
        self._brand: str | None = None
        self.runtime_cache = runtime_cache or RuntimeTagCache()

    def connect(self, brand: str, ip: str, **options) -> bool:
        self.disconnect()

        if brand == "Siemens":
            driver = SiemensS7Driver()
            connect_args = (
                ip,
                int(options.get("rack", 0)),
                int(options.get("slot", 1)),
                int(options.get("db_number", 100)),
            )
        elif brand == "Schneider":
            driver = SchneiderModbusDriver()
            connect_args = (
                ip,
                int(options.get("port", 502)),
                int(options.get("slave_id", 1)),
            )
        else:
            raise ValueError(f"Unsupported PLC brand: {brand}")

        try:
            connected = bool(driver.connect(*connect_args))
        except Exception:
            try:
                driver.disconnect()
            except Exception:
                pass
            raise

        if not connected:
            try:
                driver.disconnect()
            except Exception:
                pass
            return False

        self._driver = driver
        self._brand = brand
        return True

    def disconnect(self) -> None:
        driver = self._driver
        self._driver = None
        self._brand = None
        self.runtime_cache.invalidate_source(RuntimeValueSource.PLC)

        if driver is not None:
            try:
                driver.disconnect()
            except Exception:
                pass

    def is_connected(self) -> bool:
        if self._driver is None:
            return False

        is_connected = getattr(self._driver, "is_connected", None)
        try:
            return bool(is_connected()) if callable(is_connected) else False
        except Exception:
            return False

    def read(
        self,
        definitions: Iterable[TagDefinition],
        brand: str | None = None,
    ) -> bool:
        tags = list(definitions)
        self.runtime_cache.sync(tags)

        if not self.is_connected():
            self.runtime_cache.invalidate_source(RuntimeValueSource.PLC)
            return False

        active_brand = brand or self._brand
        if active_brand == "Siemens":
            return self._scan_siemens(tags)
        if active_brand == "Schneider":
            return self._scan_schneider(tags)
        return False

    def scan(self, definitions: Iterable[TagDefinition], brand: str | None = None) -> bool:
        """Compatibility alias for the previous polling API."""
        return self.read(definitions, brand)

    def write_bool(self, tag: TagDefinition, value: bool) -> bool | None:
        if not self.is_connected() or self._brand is None:
            return None

        try:
            if self._brand == "Siemens":
                byte_index, bit_index = _parse_siemens_address(tag)
                result = self._driver.write_digital(byte_index, bit_index, bool(value))
            else:
                address = _parse_schneider_address(tag)
                result = self._driver.write_digital(address, bool(value))
        except Exception:
            return None

        if result is not None:
            self.runtime_cache.update(
                tag.name,
                bool(result),
                RuntimeValueSource.PLC,
            )
            return bool(result)
        return None

    def write_numeric(
        self,
        target: TagDefinition | str | int,
        value: int | float,
    ) -> int | float | None:
        if not self.is_connected() or self._brand is None:
            return None

        try:
            address = self._numeric_address(target)
            result = self._driver.write_analog(address, value)
        except Exception:
            return None

        if result is not None and isinstance(target, TagDefinition):
            self.runtime_cache.update(
                target.name,
                result,
                RuntimeValueSource.PLC,
            )
        return result

    def _numeric_address(self, target: TagDefinition | str | int) -> int:
        if isinstance(target, TagDefinition):
            if target.data_type not in ("INT", "REAL"):
                raise ValueError("Numeric writes require an INT or REAL tag")
            if self._brand == "Siemens":
                address, _ = _parse_siemens_address(target)
                return address
            return _parse_schneider_address(target)

        address = str(target).strip().upper()
        if self._brand == "Siemens":
            return int(address.replace("DBW", "").replace("DBD", ""))
        return int(address.replace("%MW", "").replace("MW", ""))

    def _scan_siemens(self, tags: list[TagDefinition]) -> bool:
        parsed = []
        maximum_end = 0

        for tag in tags:
            try:
                address = _parse_siemens_address(tag)
                parsed.append((tag, address))
                maximum_end = max(maximum_end, address[0] + _data_size(tag.data_type))
            except (TypeError, ValueError):
                self.runtime_cache.invalidate(tag.name)

        if not parsed:
            return True

        data = self._driver.read_data(maximum_end)
        if data is None:
            for tag, _ in parsed:
                self.runtime_cache.invalidate(tag.name)
            return False

        for tag, (byte_index, bit_index) in parsed:
            try:
                if tag.data_type == "BOOL":
                    value = get_bool(data, byte_index, bit_index)
                elif tag.data_type == "INT":
                    value = get_int(data, byte_index)
                elif tag.data_type == "REAL":
                    value = round(get_real(data, byte_index), 3)
                else:
                    raise ValueError("Unsupported tag type")
                self.runtime_cache.update(
                    tag.name,
                    value,
                    RuntimeValueSource.PLC,
                )
            except (IndexError, TypeError, ValueError):
                self.runtime_cache.invalidate(tag.name)

        return True

    def _scan_schneider(self, tags: list[TagDefinition]) -> bool:
        coils = []
        registers = []

        for tag in tags:
            try:
                address = _parse_schneider_address(tag)
                if tag.data_type == "BOOL":
                    coils.append((tag, address))
                elif tag.data_type in ("INT", "REAL"):
                    registers.append((tag, address))
                else:
                    raise ValueError("Unsupported tag type")
            except (TypeError, ValueError):
                self.runtime_cache.invalidate(tag.name)

        success = True
        if coils:
            success = self._read_schneider_coils(coils) and success
        if registers:
            success = self._read_schneider_registers(registers) and success
        return success

    def _read_schneider_coils(self, tags) -> bool:
        start = min(address for _, address in tags)
        end = max(address for _, address in tags)
        values = self._driver.read_coils_block(start, end - start + 1)

        if values is None:
            for tag, _ in tags:
                self.runtime_cache.invalidate(tag.name)
            return False

        for tag, address in tags:
            offset = address - start
            if offset < len(values):
                self.runtime_cache.update(
                    tag.name,
                    bool(values[offset]),
                    RuntimeValueSource.PLC,
                )
            else:
                self.runtime_cache.invalidate(tag.name)
        return True

    def _read_schneider_registers(self, tags) -> bool:
        start = min(address for _, address in tags)
        end = max(
            address + (2 if tag.data_type == "REAL" else 1)
            for tag, address in tags
        )
        values = self._driver.read_registers_block(start, end - start)

        if values is None:
            for tag, _ in tags:
                self.runtime_cache.invalidate(tag.name)
            return False

        for tag, address in tags:
            offset = address - start
            try:
                if tag.data_type == "INT":
                    value = values[offset]
                else:
                    raw = struct.pack(
                        ">HH",
                        values[offset] & 0xFFFF,
                        values[offset + 1] & 0xFFFF,
                    )
                    value = round(struct.unpack(">f", raw)[0], 3)
                self.runtime_cache.update(
                    tag.name,
                    value,
                    RuntimeValueSource.PLC,
                )
            except (IndexError, struct.error):
                self.runtime_cache.invalidate(tag.name)
        return True


def _data_size(data_type: str) -> int:
    return {"BOOL": 1, "INT": 2, "REAL": 4}.get(data_type, 0)


def _parse_siemens_address(tag: TagDefinition) -> tuple[int, int | None]:
    address = tag.address.strip().upper()
    if tag.data_type == "BOOL":
        byte_text, bit_text = address.replace("DBX", "").split(".")
        bit_index = int(bit_text)
        if bit_index < 0 or bit_index > 7:
            raise ValueError("Invalid bit index")
        byte_index = int(byte_text)
        if byte_index < 0:
            raise ValueError("Invalid byte index")
        return byte_index, bit_index
    if tag.data_type == "INT":
        byte_index = int(address.replace("DBW", ""))
        if byte_index < 0:
            raise ValueError("Invalid byte index")
        return byte_index, None
    if tag.data_type == "REAL":
        byte_index = int(address.replace("DBD", ""))
        if byte_index < 0:
            raise ValueError("Invalid byte index")
        return byte_index, None
    raise ValueError("Unsupported tag type")


def _parse_schneider_address(tag: TagDefinition) -> int:
    address = tag.address.strip().upper()
    if tag.data_type == "BOOL":
        parsed = int(address.replace("%M", "").replace("M", ""))
        if parsed < 0:
            raise ValueError("Invalid coil address")
        return parsed
    if tag.data_type in ("INT", "REAL"):
        parsed = int(address.replace("%MW", "").replace("MW", ""))
        if parsed < 0:
            raise ValueError("Invalid register address")
        return parsed
    raise ValueError("Unsupported tag type")
