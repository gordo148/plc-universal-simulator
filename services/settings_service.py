"""Persistence for user-interface preferences, separate from project state."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import sys
import tempfile


SUPPORTED_BRANDS = {"Siemens", "Schneider", "Modbus TCP", "Rockwell", "Omron", "Simulator"}
DEFAULT_WINDOW_SIZE = "1500x850"
_WINDOW_SIZE_RE = re.compile(r"^\d{3,5}x\d{3,5}$")
DASHBOARD_COLUMN_IDS = ("name", "address", "type", "value", "status", "comment", "source", "alarm", "trend")
DASHBOARD_DEFAULT_WIDTHS = {"name":190,"address":135,"type":75,"value":105,"status":85,"comment":320,"source":125,"alarm":95,"trend":80}


def default_dashboard_preferences():
    return {
        "visible_columns": list(DASHBOARD_COLUMN_IDS),
        "column_order": list(DASHBOARD_COLUMN_IDS),
        "column_widths": dict(DASHBOARD_DEFAULT_WIDTHS),
        "compact_view": False,
        "sort_column": "name",
        "sort_descending": False,
    }


def normalize_dashboard_preferences(value):
    """Return a complete, safe dashboard layout while accepting old settings."""
    defaults = default_dashboard_preferences()
    if not isinstance(value, dict):
        return defaults
    order = value.get("column_order")
    order = [item for item in order if item in DASHBOARD_COLUMN_IDS] if isinstance(order, list) else []
    order = list(dict.fromkeys(order))
    order.extend(item for item in DASHBOARD_COLUMN_IDS if item not in order)
    visible = value.get("visible_columns")
    visible = [item for item in visible if item in DASHBOARD_COLUMN_IDS] if isinstance(visible, list) else list(DASHBOARD_COLUMN_IDS)
    visible = list(dict.fromkeys(visible))
    if "name" not in visible: visible.append("name")
    widths = value.get("column_widths") if isinstance(value.get("column_widths"), dict) else {}
    normalized_widths = {}
    for column, default in DASHBOARD_DEFAULT_WIDTHS.items():
        width = widths.get(column, default)
        normalized_widths[column] = max(40, min(1200, width)) if isinstance(width, int) and not isinstance(width, bool) else default
    sort_column = value.get("sort_column", "name")
    if sort_column not in ("name", "address", "type", "value", "status"): sort_column = "name"
    return {
        "visible_columns": visible,
        "column_order": order,
        "column_widths": normalized_widths,
        "compact_view": bool(value.get("compact_view", False)),
        "sort_column": sort_column,
        "sort_descending": bool(value.get("sort_descending", False)),
    }


def default_ui_preferences():
    return {"appearance_mode": "dark", "dashboard": default_dashboard_preferences()}


def default_settings_path():
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    return str(base / "config" / "settings.json")


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
            "dashboard": normalize_dashboard_preferences(preferences.get("dashboard")),
        }

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
            "dashboard": normalize_dashboard_preferences(ui_preferences.get("dashboard")),
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
