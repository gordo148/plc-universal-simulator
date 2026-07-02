import snap7
from snap7.util import set_bool, set_int, get_bool, get_int


class SiemensS7Driver:
    def __init__(self):
        self.client = snap7.client.Client()
        self.data = bytearray(1000)
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
        if not self.is_connected():
            return None

        return self.client.db_read(self.db_number, 0, size)

    def write_digital(self, byte_index, bit_index, value):
        if not self.is_connected():
            return None

        set_bool(self.data, byte_index, bit_index, value)
        self.client.db_write(self.db_number, 0, self.data)

        plc_data = self.client.db_read(self.db_number, 0, 1000)
        real_value = get_bool(plc_data, byte_index, bit_index)

        set_bool(self.data, byte_index, bit_index, real_value)
        return real_value

    def write_analog(self, byte_index, value):
        if not self.is_connected():
            return None

        value = max(-32768, min(32767, int(value)))

        set_int(self.data, byte_index, value)
        self.client.db_write(self.db_number, 0, self.data)

        plc_data = self.client.db_read(self.db_number, 0, 1000)
        real_value = get_int(plc_data, byte_index)

        set_int(self.data, byte_index, real_value)
        return real_value