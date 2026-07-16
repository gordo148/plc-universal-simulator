"""Tk-independent PLC connection configuration state."""

from dataclasses import dataclass


@dataclass
class ConnectionState:
    brand: str = "Siemens"
    communication_mode: str = "network"
    ip: str = "192.168.1.10"
    rack: str = "0"
    slot: str = "1"
    port: str = "502"
    slave_id: str = "1"
    coil_start: str = "0"
    register_start: str = "0"
    schneider_model: str = "M221"
    omron_port: str = "9600"
    destination_node: str = "0"
    source_node: str = "1"

    def set_brand(self, brand):
        self.brand = str(brand)
        self.communication_mode = "internal" if self.brand == "Simulator" else "network"

    def get(self, name, default=""):
        return str(getattr(self, name, default))

    def set(self, name, value):
        if not hasattr(self, name):
            raise KeyError(name)
        setattr(self, name, str(value))
