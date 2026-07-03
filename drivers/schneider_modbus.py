import struct
import inspect

from pymodbus.client import ModbusTcpClient


MAX_COILS_PER_READ = 2000
MAX_REGISTERS_PER_READ = 125


class SchneiderModbusDriver:
    def __init__(self):
        self.client = None
        self.slave_id = 1

    def connect(self, ip, port=502, slave_id=1):
        self.slave_id = int(slave_id)
        self.client = ModbusTcpClient(ip, port=int(port))
        return self.client.connect()

    def disconnect(self):
        if self.client:
            self.client.close()

    def is_connected(self):
        return self.client is not None and self.client.connected

    def _request(self, method_name, *args, **kwargs):
        method = getattr(self.client, method_name)
        try:
            parameters = inspect.signature(method).parameters
        except (TypeError, ValueError):
            parameters = {}

        unit_keyword = "device_id" if "device_id" in parameters else "slave"
        kwargs[unit_keyword] = self.slave_id
        return method(*args, **kwargs)

    def read_coils_block(self, start_address, count):
        if not self.is_connected():
            return None
        if not 1 <= count <= MAX_COILS_PER_READ:
            raise ValueError(
                f"Coil read count must be 1..{MAX_COILS_PER_READ}"
            )

        rd = self._request("read_coils", start_address, count=count)

        if rd.isError():
            return None

        return rd.bits

    def read_registers_block(self, start_address, count):
        if not self.is_connected():
            return None
        if not 1 <= count <= MAX_REGISTERS_PER_READ:
            raise ValueError(
                f"Register read count must be 1..{MAX_REGISTERS_PER_READ}"
            )

        rd = self._request(
            "read_holding_registers",
            start_address,
            count=count,
        )

        if rd.isError():
            return None

        values = []

        for raw in rd.registers:
            if raw > 32767:
                raw = raw - 65536
            values.append(raw)

        return values

    def write_digital(self, coil_address, value):
        if not self.is_connected():
            return None

        wr = self._request("write_coil", coil_address, value)
        if wr.isError():
            return None

        rd = self._request("read_coils", coil_address, count=1)
        if rd.isError():
            return None

        return bool(rd.bits[0])

    def write_analog(self, register_address, value, data_type="INT"):
        if not self.is_connected():
            return None

        data_type = str(data_type).strip().upper()
        if data_type == "REAL":
            raw = struct.pack(">f", float(value))
            registers = list(struct.unpack(">HH", raw))
            wr = self._request(
                "write_registers",
                register_address,
                registers,
            )
            if wr.isError():
                return None

            rd = self._request(
                "read_holding_registers",
                register_address,
                count=2,
            )
            if rd.isError() or len(rd.registers) < 2:
                return None

            read_raw = struct.pack(
                ">HH",
                rd.registers[0] & 0xFFFF,
                rd.registers[1] & 0xFFFF,
            )
            return struct.unpack(">f", read_raw)[0]

        if data_type != "INT":
            raise ValueError(f"Unsupported numeric type: {data_type}")

        value = int(value)
        value_to_write = value & 0xFFFF if value < 0 else value
        wr = self._request("write_register", register_address, value_to_write)
        if wr.isError():
            return None

        rd = self._request(
            "read_holding_registers",
            register_address,
            count=1,
        )
        if rd.isError():
            return None

        raw = rd.registers[0]
        return raw - 65536 if raw > 32767 else raw
