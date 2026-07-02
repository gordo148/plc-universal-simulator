"""Protocol-neutral access to the currently selected PLC driver."""

from typing import Any


class PLCService:
    """Hold the active PLC driver during the architecture migration."""

    def __init__(self, driver: Any | None = None) -> None:
        self._driver = driver

    def set_driver(self, driver: Any | None) -> None:
        self._driver = driver

    def get_driver(self) -> Any | None:
        return self._driver

    def is_connected(self) -> bool:
        if self._driver is None:
            return False

        is_connected = getattr(self._driver, "is_connected", None)
        return bool(is_connected()) if callable(is_connected) else False
