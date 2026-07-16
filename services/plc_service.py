"""Centralized PLC polling and runtime tag decoding."""

import logging
import re
import struct
import time
from importlib import import_module
from typing import Any, Iterable

from core.tag_model import TagDefinition
from core.tag_runtime import RuntimeTagCache, RuntimeValueSource
from drivers.siemens_address import validate_siemens_data_type


LOGGER = logging.getLogger(__name__)
MAX_COILS_PER_READ = 2000
MAX_REGISTERS_PER_READ = 125
SIEMENS_MAX_GAP = 16
SIEMENS_MAX_READ_SIZE = 200

# These names remain patchable for tests. A class is imported and cached only
# when its brand is first selected.
SiemensS7Driver = None
SchneiderModbusDriver = None
ModbusTCPDriver = None
RockwellEtherNetIPDriver = None
OmronFINSDriver = None
InternalSimulatorDriver = None

_DRIVER_IMPORTS = {
    "SiemensS7Driver": "drivers.siemens_s7",
    "SchneiderModbusDriver": "drivers.schneider_modbus",
    "ModbusTCPDriver": "drivers.modbus_tcp",
    "RockwellEtherNetIPDriver": "drivers.rockwell_enip",
    "OmronFINSDriver": "drivers.omron_fins",
    "InternalSimulatorDriver": "drivers.internal_simulator",
}


def _driver_class(class_name):
    driver_class = globals()[class_name]
    if driver_class is None:
        try:
            module = import_module(_DRIVER_IMPORTS[class_name])
        except ImportError:
            LOGGER.exception("PLC driver import failed: %s", class_name)
            raise
        driver_class = getattr(module, class_name)
        globals()[class_name] = driver_class
    return driver_class


class PLCService:
    def __init__(
        self,
        driver: Any | None = None,
        runtime_cache: RuntimeTagCache | None = None,
        *,
        siemens_max_gap: int = SIEMENS_MAX_GAP,
        siemens_max_read_size: int = SIEMENS_MAX_READ_SIZE,
    ) -> None:
        self._driver = driver
        self._brand: str | None = None
        self._simulator_driver = (
            driver
            if (
                driver is not None
                and driver.__class__.__module__ == "drivers.internal_simulator"
                and driver.__class__.__name__ == "InternalSimulatorDriver"
            )
            else None
        )
        self.runtime_cache = runtime_cache or RuntimeTagCache()
        self.siemens_max_gap = max(0, int(siemens_max_gap))
        self.siemens_max_read_size = max(4, int(siemens_max_read_size))
        self.diagnostics = {
            "read_success_count": 0, "read_error_count": 0,
            "write_success_count": 0, "write_error_count": 0,
            "reconnect_count": 0, "connect_count": 0,
            "last_read_timestamp": None, "last_write_timestamp": None,
            "last_read_duration_ms": 0.0, "last_write_duration_ms": 0.0,
            "total_read_duration_ms": 0.0, "total_write_duration_ms": 0.0,
        }

    def diagnostics_snapshot(self):
        data = dict(self.diagnostics)
        reads = data["read_success_count"] + data["read_error_count"]
        writes = data["write_success_count"] + data["write_error_count"]
        data["average_read_duration_ms"] = data["total_read_duration_ms"] / reads if reads else 0.0
        data["average_write_duration_ms"] = data["total_write_duration_ms"] / writes if writes else 0.0
        data["brand"] = self._brand
        data["connected"] = self.is_connected()
        return data

    def connect(self, brand: str, ip: str, **options) -> bool:
        if self.diagnostics["connect_count"]:
            self.diagnostics["reconnect_count"] += 1
        result = self._connect_impl(brand, ip, **options)
        self.diagnostics["connect_count"] += 1
        return result

    def _connect_impl(self, brand: str, ip: str, **options) -> bool:
        self.disconnect()
        LOGGER.info("PLC connection requested: brand=%s", brand)

        if brand == "Siemens":
            driver = _driver_class("SiemensS7Driver")()
            connect_args = (ip, int(options.get("rack", 0)), int(options.get("slot", 1)))
        elif brand == "Schneider":
            driver = _driver_class("SchneiderModbusDriver")()
            connect_args = (
                ip,
                int(options.get("port", 502)),
                int(options.get("slave_id", 1)),
            )
        elif brand == "Modbus TCP":
            driver = _driver_class("ModbusTCPDriver")()
            connect_args = (
                ip,
                int(options.get("port", 502)),
                int(options.get("slave_id", 1)),
            )
        elif brand == "Rockwell":
            driver = _driver_class("RockwellEtherNetIPDriver")()
            connect_args = (ip,)
        elif brand == "Omron":
            driver = _driver_class("OmronFINSDriver")()
            connect_args = (
                ip,
                int(options.get("port", 9600)),
                int(options.get("destination_node", 0)),
                int(options.get("source_node", 1)),
            )
        elif brand == "Simulator":
            if self._simulator_driver is None:
                self._simulator_driver = _driver_class(
                    "InternalSimulatorDriver"
                )()
            driver = self._simulator_driver
            connect_args = ()
        else:
            raise ValueError(f"Unsupported PLC brand: {brand}")

        try:
            connected = bool(driver.connect(*connect_args))
        except Exception:
            LOGGER.exception("PLC driver connection failed: brand=%s", brand)
            try:
                driver.disconnect()
            except Exception:
                LOGGER.exception("PLC cleanup failed after connection error")
            raise

        if not connected:
            LOGGER.warning("PLC connection rejected: brand=%s", brand)
            try:
                driver.disconnect()
            except Exception:
                LOGGER.exception("PLC cleanup failed after rejected connection")
            return False

        self._driver = driver
        self._brand = brand
        LOGGER.info("PLC connected: brand=%s", brand)
        return True

    def disconnect(self) -> None:
        driver = self._driver
        brand = self._brand
        self._driver = None
        self._brand = None
        self.runtime_cache.invalidate_source(RuntimeValueSource.PLC)

        if driver is not None:
            try:
                driver.disconnect()
            except Exception:
                LOGGER.exception("PLC disconnect failed")
            else:
                LOGGER.info("PLC disconnected: brand=%s", brand)

    def is_connected(self) -> bool:
        if self._driver is None:
            return False

        is_connected = getattr(self._driver, "is_connected", None)
        try:
            return bool(is_connected()) if callable(is_connected) else False
        except Exception:
            LOGGER.exception("PLC connection-state check failed")
            return False

    def read(self, definitions, brand=None):
        started = time.perf_counter()
        try:
            result = self._read_impl(definitions, brand)
        except Exception:
            self._record_io("read", False, started)
            raise
        self._record_io("read", bool(result), started)
        return result

    def _read_impl(
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
            return self._scan_modbus(tags, _parse_schneider_address)
        if active_brand == "Modbus TCP":
            return self._scan_modbus(tags, _parse_modbus_tcp_address)
        if active_brand == "Rockwell":
            return self._scan_rockwell(tags)
        if active_brand == "Omron":
            return self._scan_omron(tags)
        if active_brand == "Simulator":
            return self._scan_simulator(tags)
        return False

    def write_bool(self, tag: TagDefinition, value: bool) -> bool | None:
        started = time.perf_counter()
        result = self._write_bool_impl(tag, value)
        self._record_io("write", result is not None, started)
        return result

    def _write_bool_impl(self, tag: TagDefinition, value: bool) -> bool | None:
        if not self.is_connected() or self._brand is None:
            return None

        try:
            if self._brand == "Siemens":
                address = validate_siemens_data_type(tag.data_type, tag.address)
                if address.area == "I":
                    raise PermissionError(
                        f'Cannot write tag "{tag.name}" because {address.normalized_address} is a read-only input area.'
                    )
                result = self._driver.write_digital(address, bool(value))
            elif self._brand == "Rockwell":
                tag_name = _parse_rockwell_address(tag)
                result = self._driver.write_tag(tag_name, bool(value))
            elif self._brand == "Omron":
                address = _parse_omron_address(tag)
                result = self._driver.write_bool(address, bool(value))
            elif self._brand == "Simulator":
                result = self._driver.write(tag.address, bool(value), "BOOL")
            else:
                address = self._parse_modbus_address(tag)
                result = self._driver.write_digital(address, bool(value))
        except Exception:
            LOGGER.exception("PLC digital write failed for tag %s", tag.name)
            return None

        if result is not None:
            self.runtime_cache.update(
                tag.name,
                bool(result),
                RuntimeValueSource.PLC,
            )
            return bool(result)
        return None

    def write_numeric(self, target, value):
        started = time.perf_counter()
        result = self._write_numeric_impl(target, value)
        self._record_io("write", result is not None, started)
        return result

    def _write_numeric_impl(
        self,
        target: TagDefinition | str | int,
        value: int | float,
    ) -> int | float | None:
        if not self.is_connected() or self._brand is None:
            return None

        try:
            data_type = (
                target.data_type
                if isinstance(target, TagDefinition)
                else "INT"
            )
            if self._brand == "Rockwell":
                tag_name = (
                    target.address
                    if isinstance(target, TagDefinition)
                    else str(target).strip()
                )
                if isinstance(target, TagDefinition):
                    tag_name = _parse_rockwell_address(target)
                typed_value = (
                    float(value) if data_type == "REAL" else int(value)
                )
                result = self._driver.write_tag(tag_name, typed_value)
            elif self._brand == "Omron":
                if not isinstance(target, TagDefinition):
                    raise ValueError("Omron writes require a tag definition")
                address = _parse_omron_address(target)
                if data_type == "INT":
                    result = self._driver.write_int(address, int(value))
                elif data_type == "REAL":
                    result = self._driver.write_real(address, float(value))
                else:
                    raise ValueError("Omron numeric writes require INT or REAL")
            elif self._brand == "Simulator":
                if not isinstance(target, TagDefinition):
                    raise ValueError("Simulator writes require a tag definition")
                result = self._driver.write(
                    target.address,
                    value,
                    data_type,
                )
            elif self._brand == "Siemens":
                if not isinstance(target, TagDefinition):
                    raise ValueError("Siemens writes require a tag definition")
                address = validate_siemens_data_type(data_type, target.address)
                if address.area == "I":
                    raise PermissionError(
                        f'Cannot write tag "{target.name}" because {address.normalized_address} is a read-only input area.'
                    )
                result = self._driver.write_analog(address, value, data_type)
            else:
                address = self._numeric_address(target)
                result = self._driver.write_analog(address, value, data_type)
        except Exception:
            LOGGER.exception("PLC numeric write failed for target %s", target)
            return None

        if result is not None and isinstance(target, TagDefinition):
            self.runtime_cache.update(
                target.name,
                result,
                RuntimeValueSource.PLC,
            )
        return result

    def _record_io(self, operation, success, started):
        duration = (time.perf_counter() - started) * 1000
        prefix = "read" if operation == "read" else "write"
        self.diagnostics[f"{prefix}_{'success' if success else 'error'}_count"] += 1
        if success:
            self.diagnostics[f"last_{prefix}_timestamp"] = time.time()
        self.diagnostics[f"last_{prefix}_duration_ms"] = duration
        self.diagnostics[f"total_{prefix}_duration_ms"] += duration

    def _numeric_address(self, target: TagDefinition | str | int) -> int:
        if isinstance(target, TagDefinition):
            if target.data_type not in ("BYTE", "WORD", "INT", "DWORD", "DINT", "REAL"):
                raise ValueError("Numeric writes require a numeric tag")
            if self._brand == "Siemens":
                return validate_siemens_data_type(target.data_type, target.address).byte_offset
            return self._parse_modbus_address(target)

        address = str(target).strip().upper()
        if self._brand == "Siemens":
            raise ValueError("Siemens writes require a tag definition")
        return int(address.replace("%MW", "").replace("MW", ""))

    def _parse_modbus_address(self, tag: TagDefinition) -> int:
        if self._brand == "Modbus TCP":
            return _parse_modbus_tcp_address(tag)
        return _parse_schneider_address(tag)

    def _scan_siemens(self, tags: list[TagDefinition]) -> bool:
        snap7_util = import_module("snap7.util")
        parsed = []

        for tag in tags:
            try:
                address = validate_siemens_data_type(tag.data_type, tag.address)
                parsed.append(
                    (tag, address, address.size_bytes)
                )
            except (TypeError, ValueError):
                LOGGER.warning(
                    "Invalid Siemens tag address: name=%s address=%s",
                    tag.name,
                    tag.address,
                )
                self.runtime_cache.invalidate(tag.name)

        if not parsed:
            return True

        success = True
        ranges = _siemens_read_ranges(
            parsed,
            self.siemens_max_gap,
            self.siemens_max_read_size,
        )
        for area, db_number, start, size, range_tags in ranges:
            LOGGER.debug(
                "Siemens read: area=%s DB=%s start=%s size=%s tags=%s",
                area, db_number, start, size,
                len(range_tags),
            )
            try:
                data = self._driver.read_range(area, db_number, start, size)
                if data is None or len(data) < size:
                    raise ValueError(
                        f"expected {size} bytes, received "
                        f"{0 if data is None else len(data)}"
                    )
            except Exception:
                success = False
                affected = ", ".join(
                    f"{tag.name} ({tag.address})"
                    for tag, _address, _size in range_tags
                )
                LOGGER.exception(
                    "Siemens read failed: area=%s DB=%s start=%s size=%s "
                    "affected_tags=%s",
                    area, db_number, start, size,
                    affected,
                )
                for tag, _address, _size in range_tags:
                    self.runtime_cache.invalidate(tag.name)
                continue

            for tag, address, _size in range_tags:
                relative_offset = address.byte_offset - start
                try:
                    if tag.data_type == "BOOL":
                        value = snap7_util.get_bool(
                            data, relative_offset, address.bit_offset
                        )
                    elif tag.data_type == "BYTE":
                        value = snap7_util.get_byte(data, relative_offset)
                    elif tag.data_type == "WORD":
                        value = snap7_util.get_word(data, relative_offset)
                    elif tag.data_type == "INT":
                        value = snap7_util.get_int(data, relative_offset)
                    elif tag.data_type == "DWORD":
                        value = snap7_util.get_dword(data, relative_offset)
                    elif tag.data_type == "DINT":
                        value = snap7_util.get_dint(data, relative_offset)
                    elif tag.data_type == "REAL":
                        value = round(
                            snap7_util.get_real(data, relative_offset), 3
                        )
                    else:
                        raise ValueError("Unsupported tag type")
                    self.runtime_cache.update(
                        tag.name,
                        value,
                        RuntimeValueSource.PLC,
                    )
                except (IndexError, TypeError, ValueError):
                    success = False
                    self.runtime_cache.invalidate(tag.name)

        return success

    def _scan_modbus(self, tags: list[TagDefinition], address_parser) -> bool:
        coils = []
        registers = []

        for tag in tags:
            try:
                address = address_parser(tag)
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

    def _scan_rockwell(self, tags: list[TagDefinition]) -> bool:
        supported = [
            tag for tag in tags
            if tag.data_type in ("BOOL", "INT", "REAL")
            and re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*",
                str(tag.address).strip(),
            )
        ]
        for tag in tags:
            if tag not in supported:
                self.runtime_cache.invalidate(tag.name)

        if not supported:
            return True

        try:
            values = self._driver.read_tags(
                [tag.address for tag in supported]
            )
        except Exception:
            LOGGER.exception("Rockwell symbolic-tag read failed")
            for tag in supported:
                self.runtime_cache.invalidate(tag.name)
            return False

        success = True
        for tag in supported:
            if tag.address not in values:
                self.runtime_cache.invalidate(tag.name)
                success = False
                continue
            try:
                if tag.data_type == "BOOL":
                    value = bool(values[tag.address])
                elif tag.data_type == "INT":
                    value = int(values[tag.address])
                else:
                    value = round(float(values[tag.address]), 3)
                self.runtime_cache.update(
                    tag.name,
                    value,
                    RuntimeValueSource.PLC,
                )
            except (TypeError, ValueError):
                self.runtime_cache.invalidate(tag.name)
                success = False
        return success

    def _scan_omron(self, tags: list[TagDefinition]) -> bool:
        success = True
        for tag in tags:
            try:
                address = _parse_omron_address(tag)
                if tag.data_type == "BOOL":
                    value = self._driver.read_bool(address)
                elif tag.data_type == "INT":
                    value = self._driver.read_int(address)
                else:
                    value = self._driver.read_real(address)

                if value is None:
                    self.runtime_cache.invalidate(tag.name)
                    success = False
                    continue
                if tag.data_type == "BOOL":
                    value = bool(value)
                elif tag.data_type == "INT":
                    value = int(value)
                else:
                    value = round(float(value), 3)
                self.runtime_cache.update(
                    tag.name,
                    value,
                    RuntimeValueSource.PLC,
                )
            except Exception:
                LOGGER.exception("Omron FINS read failed for tag %s", tag.name)
                self.runtime_cache.invalidate(tag.name)
                success = False
        return success

    def _scan_simulator(self, tags: list[TagDefinition]) -> bool:
        success = True
        for tag in tags:
            try:
                value = self._driver.read(tag.address, tag.data_type)
                if value is None:
                    self.runtime_cache.invalidate(tag.name)
                    success = False
                    continue
                self.runtime_cache.update(
                    tag.name,
                    value,
                    RuntimeValueSource.PLC,
                )
            except (TypeError, ValueError):
                self.runtime_cache.invalidate(tag.name)
                success = False
        return success

    def _read_schneider_coils(self, tags) -> bool:
        success = True
        for block in _contiguous_blocks(
            tags,
            lambda _tag: 1,
            MAX_COILS_PER_READ,
        ):
            start = block[0][1]
            end = max(address + 1 for _, address in block)
            try:
                values = self._driver.read_coils_block(start, end - start)
            except Exception:
                LOGGER.exception(
                    "Schneider coil read failed at %s count %s",
                    start,
                    end - start,
                )
                values = None

            if values is None:
                success = False
                for tag, _ in block:
                    self.runtime_cache.invalidate(tag.name)
                continue

            for tag, address in block:
                offset = address - start
                if offset < len(values):
                    self.runtime_cache.update(
                        tag.name,
                        bool(values[offset]),
                        RuntimeValueSource.PLC,
                    )
                else:
                    success = False
                    self.runtime_cache.invalidate(tag.name)
        return success

    def _read_schneider_registers(self, tags) -> bool:
        success = True
        size = lambda tag: 2 if tag.data_type == "REAL" else 1
        for block in _contiguous_blocks(
            tags,
            size,
            MAX_REGISTERS_PER_READ,
        ):
            start = block[0][1]
            end = max(address + size(tag) for tag, address in block)
            try:
                values = self._driver.read_registers_block(start, end - start)
            except Exception:
                LOGGER.exception(
                    "Schneider register read failed at %s count %s",
                    start,
                    end - start,
                )
                values = None

            if values is None:
                success = False
                for tag, _ in block:
                    self.runtime_cache.invalidate(tag.name)
                continue

            for tag, address in block:
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
                    success = False
                    self.runtime_cache.invalidate(tag.name)
        return success


def _contiguous_blocks(tags, size_for_tag, maximum_count):
    """Group requested addresses without filling sparse gaps."""
    blocks = []
    current = []
    current_end = None

    for tag, address in sorted(tags, key=lambda item: item[1]):
        tag_end = address + size_for_tag(tag)
        if (
            current
            and (address > current_end or tag_end - current[0][1] > maximum_count)
        ):
            blocks.append(current)
            current = []
            current_end = None

        current.append((tag, address))
        current_end = tag_end if current_end is None else max(current_end, tag_end)

    if current:
        blocks.append(current)
    return blocks


def _siemens_read_ranges(parsed_tags, maximum_gap, maximum_size):
    """Group tags by area/DB into compact, size-limited read ranges."""
    ranges = []
    groups = {}
    for item in parsed_tags:
        groups.setdefault((item[1].area, item[1].db_number), []).append(item)
    for (area, db_number), items in groups.items():
        current, start, end = [], None, None
        for item in sorted(items, key=lambda parsed: parsed[1].byte_offset):
            tag_start = item[1].byte_offset
            tag_end = tag_start + item[2]
            if current and (tag_start - end > maximum_gap or max(end, tag_end) - start > maximum_size):
                ranges.append((area, db_number, start, end - start, current))
                current, start, end = [], None, None
            if not current:
                start, end = tag_start, tag_end
            else:
                end = max(end, tag_end)
            current.append(item)
        if current:
            ranges.append((area, db_number, start, end - start, current))
    return ranges


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


def _parse_modbus_tcp_address(tag: TagDefinition) -> int:
    address = str(tag.address).strip().upper()
    if tag.data_type == "BOOL":
        match = re.fullmatch(r"(?:%?M)?(\d+)", address)
    elif tag.data_type in ("INT", "REAL"):
        match = re.fullmatch(r"(?:%?MW)?(\d+)", address)
    else:
        raise ValueError("Unsupported tag type")

    if match is None:
        raise ValueError("Invalid Modbus TCP address")
    return int(match.group(1))


def _parse_rockwell_address(tag: TagDefinition) -> str:
    if tag.data_type not in ("BOOL", "INT", "REAL"):
        raise ValueError("Unsupported tag type")
    address = str(tag.address).strip()
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", address) is None:
        raise ValueError("Invalid Rockwell symbolic tag name")
    return address


def _parse_omron_address(tag: TagDefinition) -> str:
    address = str(tag.address).strip().upper()
    if tag.data_type == "BOOL":
        match = re.fullmatch(r"CIO\d+\.(?:0\d|1[0-5])", address)
    elif tag.data_type in ("INT", "REAL"):
        match = re.fullmatch(r"D\d+", address)
    else:
        raise ValueError("Unsupported tag type")
    if match is None:
        raise ValueError("Invalid Omron FINS address")
    return address
