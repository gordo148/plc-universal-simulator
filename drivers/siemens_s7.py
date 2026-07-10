import snap7
from snap7.util import get_bool, get_int, get_real, set_bool, set_int, set_real


class SiemensS7Driver:
    def __init__(self):
        self.client = snap7.client.Client()
        self.db_number = 100

    def connect(self, ip, rack=0, slot=1, db_number=100):
        self.db_number = int(db_number)
        self.client.connect(ip, int(rack), int(slot))
        return self.client.get_connected()

    def disconnect(self):
        self.client.disconnect()

    def is_connected(self):
        return self.client.get_connected()

    def read_data(self, size=1000):
        """Read from DB byte zero (kept for backwards compatibility)."""
        return self.read_range(0, size)

    def read_range(self, start, size):
        """Read a bounded byte range from the configured data block."""
        if not self.is_connected():
            return None

        return self.client.db_read(self.db_number, int(start), int(size))

    def write_digital(self, byte_index, bit_index, value):
        if not self.is_connected():
            return None

        data = bytearray(
            self.client.db_read(self.db_number, byte_index, 1)
        )
        if len(data) != 1:
            return None

        set_bool(data, 0, bit_index, bool(value))
        self.client.db_write(self.db_number, byte_index, data)

        plc_data = bytearray(
            self.client.db_read(self.db_number, byte_index, 1)
        )
        if len(plc_data) != 1:
            return None
        return get_bool(plc_data, 0, bit_index)

    def write_analog(self, byte_index, value, data_type="INT"):
        if not self.is_connected():
            return None

        data_type = str(data_type).strip().upper()
        if data_type == "INT":
            size = 2
        elif data_type == "REAL":
            size = 4
        else:
            raise ValueError(f"Unsupported numeric type: {data_type}")

        data = bytearray(
            self.client.db_read(self.db_number, byte_index, size)
        )
        if len(data) != size:
            return None

        if data_type == "INT":
            encoded_value = max(-32768, min(32767, int(value)))
            set_int(data, 0, encoded_value)
        else:
            set_real(data, 0, float(value))

        self.client.db_write(self.db_number, byte_index, data)

        plc_data = bytearray(
            self.client.db_read(self.db_number, byte_index, size)
        )
        if len(plc_data) != size:
            return None
        if data_type == "INT":
            return get_int(plc_data, 0)
        return get_real(plc_data, 0)
