"""Persistence for user-interface preferences, separate from project state."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from core.dashboard_model import (
    default_dashboard_preferences,
    normalize_dashboard_preferences,
)


SUPPORTED_BRANDS = {"Siemens", "Schneider", "Modbus TCP", "Rockwell", "Omron", "Simulator"}
DEFAULT_WINDOW_SIZE = "1500x850"
_WINDOW_SIZE_RE = re.compile(r"^\d{3,5}x\d{3,5}$")
def default_ui_preferences():
    return {"appearance_mode": "dark", "dashboard_ui": default_dashboard_preferences()}


def default_settings_path():
    if getattr(sys, "frozen", False):
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or Path.home())
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
        return str(base / "plc-universal-simulator" / "settings.json")
    return str(Path(__file__).resolve().parent.parent / "config" / "settings.json")


def legacy_frozen_settings_path():
    return str(Path(sys.executable).resolve().parent / "config" / "settings.json")


@dataclass
class ApplicationSettings:
    plc_brand: str = "Siemens"
    ip_address: str = "192.168.1.10"
    last_project_path: str | None = None
    window_size: str = DEFAULT_WINDOW_SIZE
    recent_projects: list[str] = field(default_factory=list)
    last_project_folder: str = "configs/projects"
    ui_preferences: dict = field(
        default_factory=default_ui_preferences
    )

    def __post_init__(self):
        preferences = self.ui_preferences if isinstance(self.ui_preferences, dict) else {}
        appearance = preferences.get("appearance_mode", "dark")
        if appearance not in ("dark", "light", "system"): appearance = "dark"
        self.ui_preferences = {
            "appearance_mode": appearance,
            "dashboard_ui": normalize_dashboard_preferences(
                preferences.get("dashboard_ui", preferences.get("dashboard"))
            ),
        }

    @classmethod
    def load(cls, path=None):
        settings_path = path or default_settings_path()
        if path is None and getattr(sys,"frozen",False) and not os.path.exists(settings_path):
            legacy = legacy_frozen_settings_path()
            if os.path.exists(legacy): settings_path=legacy
        try:
            with open(settings_path, "r", encoding="utf-8") as handle:
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
        project_folder = data.get("last_project_folder", "configs/projects")
        if not isinstance(project_folder, str) or not project_folder:
            project_folder = "configs/projects"
        ui_preferences = data.get("ui_preferences", default_ui_preferences())
        if not isinstance(ui_preferences, dict):
            ui_preferences = default_ui_preferences()
        appearance_mode = ui_preferences.get("appearance_mode", "dark")
        if appearance_mode not in ("dark", "light", "system"):
            appearance_mode = "dark"
        ui_preferences = {
            "appearance_mode": appearance_mode,
            "dashboard_ui": normalize_dashboard_preferences(
                ui_preferences.get("dashboard_ui", ui_preferences.get("dashboard"))
            ),
        }
        return cls(
            brand,
            ip,
            last,
            size,
            recent,
            project_folder,
            ui_preferences,
        )

    def add_recent_project(self, path):
        normalized = os.path.abspath(os.path.expanduser(path))
        self.recent_projects = [normalized] + [
            item for item in self.recent_projects if item != normalized
        ]
        self.recent_projects = self.recent_projects[:5]
        self.last_project_path = normalized
        self.last_project_folder = os.path.dirname(normalized)

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
            "last_project_folder": self.last_project_folder,
            "ui_preferences": self.ui_preferences,
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
