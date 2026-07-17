"""Pure Dashboard v2 presentation state, filtering and sorting helpers."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Iterable, Mapping


DASHBOARD_PREFERENCE_VERSION = 1
COMPACT_COLUMNS = ("status", "name", "value", "comment")
SORTABLE_COLUMNS = frozenset(("name", "address", "type", "value", "status"))
_NATURAL_PARTS = re.compile(r"(\d+)")


@dataclass(frozen=True)
class DashboardColumn:
    key: str
    label: str
    default_visible: bool
    default_width: int
    minimum_width: int
    maximum_width: int
    sortable: bool = False


COLUMN_REGISTRY = (
    DashboardColumn("status", "Status", True, 85, 65, 150, True),
    DashboardColumn("name", "Name", True, 190, 100, 500, True),
    DashboardColumn("address", "Address", False, 135, 80, 400, True),
    DashboardColumn("comment", "Comment", False, 320, 100, 600),
    DashboardColumn("type", "Type", True, 75, 60, 160, True),
    DashboardColumn("value", "Value", True, 105, 70, 260, True),
    DashboardColumn("source", "Source", False, 125, 80, 240),
    DashboardColumn("alarm", "Alarm", True, 95, 65, 160),
    DashboardColumn("trend", "Trend", True, 80, 60, 140),
)
COLUMNS_BY_KEY = {column.key: column for column in COLUMN_REGISTRY}
COLUMN_KEYS = tuple(COLUMNS_BY_KEY)
DEFAULT_VISIBLE_COLUMNS = tuple(
    column.key for column in COLUMN_REGISTRY if column.default_visible
)
DEFAULT_WIDTHS = {
    column.key: column.default_width for column in COLUMN_REGISTRY
}


def _default_full_layout():
    return {
        "visible": list(DEFAULT_VISIBLE_COLUMNS),
        "order": list(COLUMN_KEYS),
        "widths": dict(DEFAULT_WIDTHS),
    }


def default_dashboard_preferences():
    """Return a new complete Dashboard preference structure."""
    return {
        "version": DASHBOARD_PREFERENCE_VERSION,
        "compact": False,
        "full_layout": _default_full_layout(),
        "previous_full_layout": _default_full_layout(),
        "sort": {"column": "name", "descending": False},
        "filters": {
            "statuses": [], "features": [], "types": [],
        },
        "splitter": 0.72,
    }


def clamp_column_width(column: str, width: Any) -> int:
    definition = COLUMNS_BY_KEY[column]
    if not isinstance(width, int) or isinstance(width, bool):
        return definition.default_width
    return max(definition.minimum_width, min(definition.maximum_width, width))


def _validated_layout(raw: Any, fallback: Mapping[str, Any] | None = None):
    fallback = fallback or _default_full_layout()
    raw = raw if isinstance(raw, Mapping) else {}
    order = raw.get("order", fallback.get("order", COLUMN_KEYS))
    order = [key for key in order if key in COLUMNS_BY_KEY] if isinstance(order, (list, tuple)) else []
    order = list(dict.fromkeys(order))
    order.extend(key for key in COLUMN_KEYS if key not in order)
    visible = raw.get("visible", fallback.get("visible", DEFAULT_VISIBLE_COLUMNS))
    visible = [key for key in visible if key in COLUMNS_BY_KEY] if isinstance(visible, (list, tuple)) else []
    visible = list(dict.fromkeys(visible))
    if "name" not in visible:
        visible.append("name")
    if not visible:
        visible = ["name"]
    widths = raw.get("widths", fallback.get("widths", {}))
    widths = widths if isinstance(widths, Mapping) else {}
    return {
        "visible": visible,
        "order": order,
        "widths": {
            key: clamp_column_width(key, widths.get(key, DEFAULT_WIDTHS[key]))
            for key in COLUMN_KEYS
        },
    }


def _migrate_legacy_preferences(raw: Mapping[str, Any]):
    """Migrate the unversioned column draft used by pre-v2 worktrees."""
    if not any(key in raw for key in ("visible_columns", "column_order", "column_widths", "compact_view")):
        return raw
    layout = {
        "visible": raw.get("visible_columns"),
        "order": raw.get("column_order"),
        "widths": raw.get("column_widths"),
    }
    return {
        "version": DASHBOARD_PREFERENCE_VERSION,
        "compact": raw.get("compact_view", False),
        "full_layout": layout,
        "previous_full_layout": layout,
        "sort": {
            "column": raw.get("sort_column", "name"),
            "descending": raw.get("sort_descending", False),
        },
    }


def normalize_dashboard_preferences(raw: Any):
    """Validate/migrate preferences, recovering invalid subfields safely."""
    defaults = default_dashboard_preferences()
    if not isinstance(raw, Mapping):
        return defaults
    raw = _migrate_legacy_preferences(raw)
    full_layout = _validated_layout(raw.get("full_layout"), defaults["full_layout"])
    previous = _validated_layout(raw.get("previous_full_layout"), full_layout)
    sort = raw.get("sort") if isinstance(raw.get("sort"), Mapping) else {}
    sort_column = sort.get("column", "name")
    if sort_column not in SORTABLE_COLUMNS:
        sort_column = "name"
    filters = raw.get("filters") if isinstance(raw.get("filters"), Mapping) else {}
    statuses = _known_values(filters.get("statuses"), ("GOOD", "BAD"))
    features = _known_values(filters.get("features"), ("simulation", "trend", "alarm"))
    types = filters.get("types") if isinstance(filters.get("types"), (list, tuple, set)) else ()
    types = list(dict.fromkeys(str(item).strip().upper() for item in types if str(item).strip()))
    splitter = raw.get("splitter", defaults["splitter"])
    if not isinstance(splitter, (int, float)) or isinstance(splitter, bool) or not math.isfinite(splitter):
        splitter = defaults["splitter"]
    return {
        "version": DASHBOARD_PREFERENCE_VERSION,
        "compact": bool(raw.get("compact", False)),
        "full_layout": full_layout,
        "previous_full_layout": previous,
        "sort": {"column": sort_column, "descending": bool(sort.get("descending", False))},
        "filters": {"statuses": statuses, "features": features, "types": types},
        "splitter": max(0.35, min(0.85, float(splitter))),
    }


def _known_values(raw: Any, allowed: Iterable[str]):
    allowed = tuple(allowed)
    values = raw if isinstance(raw, (list, tuple, set)) else ()
    return list(dict.fromkeys(item for item in values if item in allowed))


def ordered_visible_columns(preferences: Mapping[str, Any]):
    """Return validated Treeview displaycolumns for the active view."""
    preferences = normalize_dashboard_preferences(preferences)
    if preferences["compact"]:
        return COMPACT_COLUMNS
    layout = preferences["full_layout"]
    visible = set(layout["visible"])
    return tuple(key for key in layout["order"] if key in visible)


def set_column_visibility(preferences: Mapping[str, Any], column: str, visible: bool):
    updated = normalize_dashboard_preferences(preferences)
    if column not in COLUMNS_BY_KEY or (column == "name" and not visible):
        return updated
    columns = list(updated["full_layout"]["visible"])
    if visible and column not in columns:
        columns.append(column)
    elif not visible and column in columns and len(columns) > 1:
        columns.remove(column)
    updated["full_layout"]["visible"] = columns
    return updated


def move_visible_column(preferences: Mapping[str, Any], column: str, offset: int):
    updated = normalize_dashboard_preferences(preferences)
    visible_order = list(ordered_visible_columns({**updated, "compact": False}))
    if column not in visible_order:
        return updated
    source = visible_order.index(column)
    target = max(0, min(len(visible_order) - 1, source + int(offset)))
    if source == target:
        return updated
    visible_order.insert(target, visible_order.pop(source))
    iterator = iter(visible_order)
    visible = set(visible_order)
    updated["full_layout"]["order"] = [next(iterator) if key in visible else key for key in updated["full_layout"]["order"]]
    return updated


def calculate_auto_fit_width(header, values, measure, minimum, maximum, sample_limit=500):
    """Measure a bounded visible sample and clamp its padded column width."""
    widest = measure(str(header))
    for index, value in enumerate(values):
        if index >= max(1, int(sample_limit)):
            break
        widest = max(widest, measure("" if value is None else str(value)))
    return max(int(minimum), min(int(maximum), int(widest) + 24))


def searchable_tag_text(tag: Any) -> str:
    return "\n".join(
        _safe_text(getattr(tag, field, "")).casefold()
        for field in ("name", "address", "comment", "data_type")
    )


def filter_dashboard_population(tags, query="", filters=None, runtime=None):
    """Apply deterministic text/status/feature/type filters."""
    state = normalize_dashboard_preferences({"filters": filters or {}})["filters"]
    query = _safe_text(query).strip().casefold()
    statuses, features, types = set(state["statuses"]), set(state["features"]), set(state["types"])
    result = []
    for tag in tags:
        if query and query not in searchable_tag_text(tag):
            continue
        item = runtime.get(getattr(tag, "name", "")) if runtime is not None else None
        status = "GOOD" if item is not None and bool(getattr(item, "valid", False)) else "BAD"
        if statuses and status not in statuses:
            continue
        if "simulation" in features and not bool(getattr(tag, "enabled_sim", False)):
            continue
        if "trend" in features and not bool(getattr(tag, "enabled_trend", False)):
            continue
        if "alarm" in features and not bool(getattr(tag, "enabled_alarm", False)):
            continue
        if types and _safe_text(getattr(tag, "data_type", "")).upper() not in types:
            continue
        result.append(tag)
    return result


def sort_dashboard_population(tags, column, descending=False, runtime=None):
    """Sort known values type-correctly and keep unavailable values last."""
    column = column if column in SORTABLE_COLUMNS else "name"
    known, missing = [], []
    for tag in tags:
        key = dashboard_sort_value(tag, column, runtime)
        (missing if key is None else known).append((key, tag))
    known.sort(key=lambda pair: pair[0], reverse=bool(descending))
    return [tag for _, tag in known] + [tag for _, tag in missing]


def dashboard_sort_value(tag, column, runtime=None):
    if column == "name": return _natural_key(getattr(tag, "name", ""))
    if column == "address": return _natural_key(getattr(tag, "address", ""))
    if column == "type": return _natural_key(getattr(tag, "data_type", ""))
    item = runtime.get(getattr(tag, "name", "")) if runtime is not None else None
    if column == "status": return 1 if item is not None and bool(getattr(item, "valid", False)) else 0
    if item is None or not bool(getattr(item, "valid", False)):
        return None
    value = getattr(item, "value", None)
    if value is None: return None
    if isinstance(value, bool): return (0, int(value))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (1, float(value)) if math.isfinite(float(value)) else None
    return (2, _safe_text(value).casefold())


def dashboard_statistics(tags, runtime=None):
    tags = list(tags)
    good = 0
    for tag in tags:
        item = runtime.get(getattr(tag, "name", "")) if runtime is not None else None
        good += int(item is not None and bool(getattr(item, "valid", False)))
    return {
        "total": len(tags), "good": good, "bad": len(tags) - good,
        "simulation": sum(bool(getattr(tag, "enabled_sim", False)) for tag in tags),
        "trend": sum(bool(getattr(tag, "enabled_trend", False)) for tag in tags),
        "alarm": sum(bool(getattr(tag, "enabled_alarm", False)) for tag in tags),
    }


def _natural_key(value: Any):
    return tuple(int(part) if part.isdigit() else part.casefold() for part in _NATURAL_PARTS.split(_safe_text(value)))


def _safe_text(value: Any) -> str:
    return "" if value is None else str(value)
