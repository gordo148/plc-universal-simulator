"""Generic Modbus TCP driver.

The wire protocol and value encoding are identical to the existing Schneider
driver.  Brand-specific address syntax is handled by PLCService, not here.
"""

from drivers.schneider_modbus import SchneiderModbusDriver


class ModbusTCPDriver(SchneiderModbusDriver):
    """Generic Modbus TCP coils and holding-register transport."""

