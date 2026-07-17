from dataclasses import dataclass, field

from core.tag_identity import generate_tag_id, normalize_tag_id


SIEMENS_NUMERIC_TYPES = ("BYTE", "WORD", "INT", "DWORD", "DINT", "REAL")


@dataclass
class TagDefinition:
    name: str
    data_type: str
    direction: str
    address: str
    enabled_sim: bool = False
    enabled_trend: bool = False
    enabled_alarm: bool = False
    enabled_dashboard: bool = False
    comment: str = ""
    tag_id: str = field(default_factory=generate_tag_id, compare=False)

    def __post_init__(self):
        self.comment = "" if self.comment is None else str(self.comment)
        self.tag_id = normalize_tag_id(self.tag_id)

    def to_dict(self):
        return {
            "tag_id": normalize_tag_id(self.tag_id),
            "name": self.name,
            "data_type": self.data_type,
            "direction": self.direction,
            "address": self.address,
            "enabled_sim": self.enabled_sim,
            "enabled_trend": self.enabled_trend,
            "enabled_alarm": self.enabled_alarm,
            "enabled_dashboard": self.enabled_dashboard,
            "comment": self.comment,
        }

    @staticmethod
    def from_dict(data):
        values = {
            "name": data.get("name", ""),
            "data_type": data.get("data_type", "BOOL"),
            "direction": data.get("direction", "Input"),
            "address": data.get("address", ""),
            "enabled_sim": data.get("enabled_sim", False),
            "enabled_trend": data.get("enabled_trend", False),
            "enabled_alarm": data.get("enabled_alarm", False),
            "enabled_dashboard": data.get("enabled_dashboard", False),
            "comment": data.get("comment") or "",
        }
        if "tag_id" in data:
            values["tag_id"] = data["tag_id"]
        return TagDefinition(**values)


# Backwards-compatible name used by the existing UI and project files.
Tag = TagDefinition
