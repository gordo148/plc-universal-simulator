"""Rockwell EtherNet/IP symbolic-tag driver."""

from typing import Any, Iterable

from pycomm3 import LogixDriver


class RockwellEtherNetIPDriver:
    def __init__(self) -> None:
        self.client = None

    def connect(self, ip: str) -> bool:
        self.client = LogixDriver(ip)
        return bool(self.client.open())

    def disconnect(self) -> None:
        if self.client is not None:
            self.client.close()

    def is_connected(self) -> bool:
        return self.client is not None and bool(self.client.connected)

    def read_tags(self, names: Iterable[str]) -> dict[str, Any]:
        names = list(names)
        if not names or not self.is_connected():
            return {}

        responses = self.client.read(*names)
        if len(names) == 1:
            responses = [responses]

        return {
            name: response.value
            for name, response in zip(names, responses)
            if response is not None and response.error is None
        }

    def write_tag(self, name: str, value: Any) -> Any | None:
        if not self.is_connected():
            return None

        response = self.client.write((name, value))
        if response is None or response.error is not None:
            return None
        return response.value
