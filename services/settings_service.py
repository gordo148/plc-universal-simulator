"""Persistence for user-interface preferences, separate from project state."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import re
import tempfile


SUPPORTED_BRANDS = {"Siemens", "Schneider", "Modbus TCP", "Rockwell", "Omron", "Simulator"}
DEFAULT_WINDOW_SIZE = "1500x850"
_WINDOW_SIZE_RE = re.compile(r"^\d{3,5}x\d{3,5}$")


def default_settings_path():
    base = os.environ.get("XDG_CONFIG_HOME")
    if not base and os.name == "nt":
        base = os.environ.get("APPDATA")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "plc-universal-simulator", "settings.json")


@dataclass
class ApplicationSettings:
    plc_brand: str = "Siemens"
    ip_address: str = "192.168.1.10"
    last_project_path: str | None = None
    window_size: str = DEFAULT_WINDOW_SIZE
    recent_projects: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path=None):
        try:
            with open(path or default_settings_path(), "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return cls._from_dict(data) if isinstance(data, dict) else cls()
        except (OSError, ValueError, TypeError):
            return cls()

    @classmethod
    def _from_dict(cls, data):
        brand = data.get("plc_brand", "Siemens")
        if brand not in SUPPORTED_BRANDS:
            brand = "Siemens"
        ip = data.get("ip_address", "192.168.1.10")
        if not isinstance(ip, str):
            ip = "192.168.1.10"
        size = data.get("window_size", DEFAULT_WINDOW_SIZE)
        if not isinstance(size, str) or not _WINDOW_SIZE_RE.fullmatch(size):
            size = DEFAULT_WINDOW_SIZE
        last = data.get("last_project_path")
        if not isinstance(last, str) or not last:
            last = None
        recent = []
        items = data.get("recent_projects", [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, str) and item and item not in recent:
                    recent.append(item)
                if len(recent) == 5:
                    break
        return cls(brand, ip, last, size, recent)

    def add_recent_project(self, path):
        normalized = os.path.abspath(os.path.expanduser(path))
        self.recent_projects = [normalized] + [
            item for item in self.recent_projects if item != normalized
        ]
        self.recent_projects = self.recent_projects[:5]
        self.last_project_path = normalized

    def save(self, path=None):
        settings_path = path or default_settings_path()
        directory = os.path.dirname(settings_path)
        os.makedirs(directory, exist_ok=True)
        payload = {
            "plc_brand": self.plc_brand,
            "ip_address": self.ip_address,
            "last_project_path": self.last_project_path,
            "window_size": self.window_size,
            "recent_projects": self.recent_projects[:5],
        }
        descriptor, temporary_path = tempfile.mkstemp(prefix=".settings-", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, settings_path)
        except Exception:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
            raise
