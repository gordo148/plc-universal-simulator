"""Omron FINS/UDP driver for CIO bits and DM numeric values."""

import struct

try:
    from fins import FinsClient
except ImportError:
    FinsClient = None


FINS_DEPENDENCY_ERROR = (
    "Omron FINS support requires the optional 'fins-driver' package. "
    "Install it with: pip install fins-driver"
)


class OmronFINSDriver:
    def __init__(self) -> None:
        self.client = None
        self._connected = False

    def connect(
        self,
        ip: str,
        port: int = 9600,
        destination_node: int = 0,
        source_node: int = 1,
    ) -> bool:
        if FinsClient is None:
            raise RuntimeError(FINS_DEPENDENCY_ERROR)

        port = int(port)
        destination_node = int(destination_node)
        source_node = int(source_node)
        if not 1 <= port <= 65535:
            raise ValueError("FINS port must be 1..65535")
        if not 0 <= destination_node <= 255:
            raise ValueError("FINS destination node must be 0..255")
        if not 0 <= source_node <= 255:
            raise ValueError("FINS source node must be 0..255")

        client = FinsClient(host=ip, port=port, mode="udp")
        client.da1 = destination_node
        client.sa1 = source_node
        client.connect()
        self.client = client
        self._connected = True
        return True

    def disconnect(self) -> None:
        client = self.client
        self.client = None
        self._connected = False
        if client is not None:
            client.close()

    def is_connected(self) -> bool:
        return self._connected and self.client is not None

    def read_bool(self, address: str) -> bool | None:
        response = self._read(address)
        if response is None or len(response) < 1:
            return None
        return bool(response[0])

    def write_bool(self, address: str, value: bool) -> bool | None:
        if not self._write(address, b"\x01" if value else b"\x00"):
            return None
        return bool(value)

    def read_int(self, address: str) -> int | None:
        response = self._read(address)
        if response is None or len(response) < 2:
            return None
        return struct.unpack(">h", response[:2])[0]

    def write_int(self, address: str, value: int) -> int | None:
        encoded = struct.pack(">h", int(value))
        if not self._write(address, encoded):
            return None
        return int(value)

    def read_real(self, address: str) -> float | None:
        response = self._read(address, num_items=2)
        if response is None or len(response) < 4:
            return None
        high_word_first = response[2:4] + response[0:2]
        return struct.unpack(">f", high_word_first)[0]

    def write_real(self, address: str, value: float) -> float | None:
        high_word_first = struct.pack(">f", float(value))
        low_word_first = high_word_first[2:4] + high_word_first[0:2]
        if not self._write(address, low_word_first, num_items=2):
            return None
        return float(value)

    def _read(self, address: str, num_items: int = 1) -> bytes | None:
        if not self.is_connected():
            return None
        response = self.client.memory_area_read(address, num_items=num_items)
        return response.data if response.ok else None

    def _write(
        self,
        address: str,
        data: bytes,
        num_items: int = 1,
    ) -> bool:
        if not self.is_connected():
            return False
        response = self.client.memory_area_write(
            address,
            data,
            num_items=num_items,
        )
        return bool(response.ok)
