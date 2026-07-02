from pymodbus.client import ModbusTcpClient


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

    def read_coils_block(self, start_address, count):
        if not self.is_connected():
            return None

        rd = self.client.read_coils(start_address, count=count, slave=self.slave_id)

        if rd.isError():
            return None

        return rd.bits

    def read_registers_block(self, start_address, count):
        if not self.is_connected():
            return None

        rd = self.client.read_holding_registers(start_address, count=count, slave=self.slave_id)

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

        wr = self.client.write_coil(coil_address, value, slave=self.slave_id)
        if wr.isError():
            return None

        rd = self.client.read_coils(coil_address, count=1, slave=self.slave_id)
        if rd.isError():
            return None

        return bool(rd.bits[0])

    def write_analog(self, register_address, value):
        if not self.is_connected():
            return None

        value = int(value)
        value_to_write = value & 0xFFFF if value < 0 else value

        wr = self.client.write_register(register_address, value_to_write, slave=self.slave_id)
        if wr.isError():
            return None

        rd = self.client.read_holding_registers(register_address, count=1, slave=self.slave_id)
        if rd.isError():
            return None

        raw = rd.registers[0]
        return raw - 65536 if raw > 32767 else raw