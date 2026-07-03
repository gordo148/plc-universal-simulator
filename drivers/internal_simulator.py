"""In-process PLC simulator with typed volatile memory."""

from typing import Any


class InternalSimulatorDriver:
    def __init__(self) -> None:
        self._connected = False
        self._memory: dict[str, Any] = {}

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def read(self, address: str, data_type: str) -> bool | int | float | None:
        if not self._connected:
            return None
        address = self._address(address)
        data_type = self._data_type(data_type)
        if address not in self._memory:
            self._memory[address] = self._default(data_type)
        return self._coerce(self._memory[address], data_type)

    def write(
        self,
        address: str,
        value: Any,
        data_type: str,
    ) -> bool | int | float | None:
        if not self._connected:
            return None
        address = self._address(address)
        data_type = self._data_type(data_type)
        typed_value = self._coerce(value, data_type)
        self._memory[address] = typed_value
        return typed_value

    @staticmethod
    def _address(address: str) -> str:
        address = str(address).strip()
        if not address:
            raise ValueError("Simulator address cannot be empty")
        return address

    @staticmethod
    def _data_type(data_type: str) -> str:
        data_type = str(data_type).strip().upper()
        if data_type not in ("BOOL", "INT", "REAL"):
            raise ValueError(f"Unsupported simulator data type: {data_type}")
        return data_type

    @staticmethod
    def _default(data_type: str) -> bool | int | float:
        return {"BOOL": False, "INT": 0, "REAL": 0.0}[data_type]

    @staticmethod
    def _coerce(value: Any, data_type: str) -> bool | int | float:
        if data_type == "BOOL":
            return bool(value)
        if data_type == "INT":
            return int(value)
        return float(value)
