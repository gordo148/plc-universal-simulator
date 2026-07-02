from dataclasses import dataclass, asdict, field
from typing import Any


@dataclass
class Tag:
    name: str
    data_type: str
    direction: str
    address: str
    enabled_sim: bool = False
    enabled_trend: bool = False
    enabled_alarm: bool = False
    enabled_dashboard: bool = False
    value: Any = field(default=0, repr=False, compare=False)

    def to_dict(self):
        data = asdict(self)
        data.pop("value", None)
        return data

    @staticmethod
    def from_dict(data):
        return Tag(
            name=data.get("name", ""),
            data_type=data.get("data_type", "BOOL"),
            direction=data.get("direction", "Input"),
            address=data.get("address", ""),
            enabled_sim=data.get("enabled_sim", False),
            enabled_trend=data.get("enabled_trend", False),
            enabled_alarm=data.get("enabled_alarm", False),
            enabled_dashboard=data.get("enabled_dashboard", False),
        )
