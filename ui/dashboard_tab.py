import time

import customtkinter as ctk

from ui.tag_manager import get_dashboard_tags
from ui.scrollable_frame import SafeScrollableFrame


DASHBOARD_REFRESH_MS = 500
DIGITAL_COLUMNS = 6
NUMERIC_COLUMNS = 4
EVENT_LIMIT = 100
COLOR_DASHBOARD = "#0f1720"
COLOR_CARD = "#182431"
COLOR_CARD_BORDER = "#334155"
COLOR_MUTED = "#8fa3b8"
COLOR_CYAN = "#22d3ee"
COLOR_GREEN = "#22c55e"
COLOR_RED = "#ef4444"
COLOR_AMBER = "#f59e0b"


def create_dashboard_tab(app):
    app.dashboard_events = []
    app.dashboard_frame = ctk.CTkFrame(
        app.tab_dashboard,
        fg_color=COLOR_DASHBOARD,
        corner_radius=10,
    )
    app.dashboard_frame.pack(fill="both", expand=True, padx=20, pady=20)

    ctk.CTkLabel(
        app.dashboard_frame,
        text="OPERATIONS OVERVIEW",
        font=("Arial", 26, "bold"),
        text_color="#dbeafe",
    ).pack(pady=(16, 2))
    ctk.CTkLabel(
        app.dashboard_frame,
        text="LIVE PROCESS STATUS  •  RUNTIME TAG MONITOR",
        font=("Arial", 11, "bold"),
        text_color=COLOR_MUTED,
    ).pack(pady=(0, 10))

    create_section_title(app.dashboard_frame, "CONTROL / PID")
    control_frame = ctk.CTkFrame(
        app.dashboard_frame,
        fg_color="transparent",
    )
    control_frame.pack(fill="x", padx=20, pady=(0, 5))
    app.card_alarm = create_value_card(
        control_frame,
        "ALARM SUMMARY",
        "NORMAL",
        COLOR_GREEN,
        0,
        accent=COLOR_GREEN,
    )
    app.card_pid = create_value_card(
        control_frame,
        "PID CONTROLLER",
        "OFF",
        COLOR_MUTED,
        1,
    )

    app.dashboard_tags_frame = SafeScrollableFrame(
        app.dashboard_frame,
        fg_color="#111c27",
        corner_radius=10,
    )
    app.dashboard_tags_frame.pack(
        fill="both",
        expand=True,
        padx=20,
        pady=(5, 8),
    )

    create_section_title(
        app.dashboard_tags_frame,
        "DIGITAL STATUS",
        use_grid=True,
        row=0,
    )
    app.dashboard_digital_frame = ctk.CTkFrame(
        app.dashboard_tags_frame,
        fg_color="transparent",
    )
    app.dashboard_digital_frame.grid(
        row=1,
        column=0,
        sticky="ew",
        padx=8,
        pady=(0, 8),
    )

    create_section_title(
        app.dashboard_tags_frame,
        "PROCESS VALUES",
        use_grid=True,
        row=2,
    )
    app.dashboard_numeric_frame = ctk.CTkFrame(
        app.dashboard_tags_frame,
        fg_color="transparent",
    )
    app.dashboard_numeric_frame.grid(
        row=3,
        column=0,
        sticky="ew",
        padx=8,
        pady=(0, 8),
    )
    app.dashboard_tags_frame.grid_columnconfigure(0, weight=1)
    app.dashboard_tag_cards = {}
    app.dashboard_tag_signature = None

    create_section_title(app.dashboard_frame, "EVENT LOG")
    app.dashboard_event_log = ctk.CTkTextbox(
        app.dashboard_frame,
        height=105,
        corner_radius=8,
        fg_color="#0b131c",
        border_width=1,
        border_color=COLOR_CARD_BORDER,
        text_color="#cbd5e1",
        font=("Consolas", 12),
        activate_scrollbars=True,
    )
    app.dashboard_event_log.pack(fill="x", padx=20, pady=(0, 16))
    app.dashboard_event_log.configure(state="disabled")

    record_dashboard_event(app, "Dashboard ready")
    update_dashboard(app)
    app.app.after(
        DASHBOARD_REFRESH_MS,
        lambda: refresh_dashboard(app),
    )


def create_section_title(parent, text, use_grid=False, row=0):
    label = ctk.CTkLabel(
        parent,
        text=text,
        font=("Arial", 14, "bold"),
        text_color="#dbeafe",
        anchor="w",
    )
    if use_grid:
        label.grid(row=row, column=0, sticky="ew", padx=12, pady=(10, 4))
    else:
        label.pack(fill="x", padx=24, pady=(8, 3))
    return label


def create_value_card(
    parent,
    title,
    value,
    color,
    column,
    row=0,
    accent=COLOR_CARD_BORDER,
    subtitle=None,
):
    card = ctk.CTkFrame(
        parent,
        corner_radius=10,
        fg_color=COLOR_CARD,
        border_width=2,
        border_color=accent,
    )
    card.grid(row=row, column=column, padx=8, pady=6, sticky="nsew")
    parent.grid_columnconfigure(column, weight=1)

    ctk.CTkLabel(
        card,
        text=title,
        font=("Arial", 12, "bold"),
        text_color=COLOR_MUTED,
    ).pack(pady=(12, 2))
    value_label = ctk.CTkLabel(
        card,
        text=value,
        font=("Arial", 22, "bold"),
        text_color=color,
    )
    value_label.pack(pady=(2, 3 if subtitle else 12))

    if subtitle:
        ctk.CTkLabel(
            card,
            text=subtitle,
            font=("Arial", 10),
            text_color=COLOR_MUTED,
        ).pack(pady=(0, 9))

    value_label.card_frame = card
    return value_label


def create_digital_card(parent, tag, column, row):
    card = ctk.CTkFrame(
        parent,
        corner_radius=8,
        fg_color=COLOR_CARD,
        border_width=1,
        border_color=COLOR_CARD_BORDER,
    )
    card.grid(row=row, column=column, padx=5, pady=5, sticky="nsew")
    parent.grid_columnconfigure(column, weight=1)

    ctk.CTkLabel(
        card,
        text=tag.name,
        font=("Arial", 11, "bold"),
        text_color="#dbeafe",
    ).pack(pady=(8, 1))
    state_label = ctk.CTkLabel(
        card,
        text="● ---",
        font=("Arial", 16, "bold"),
        text_color=COLOR_MUTED,
    )
    state_label.pack(pady=1)
    metadata = create_runtime_metadata(card, tag.address)

    return {
        "frame": card,
        "value": state_label,
        **metadata,
    }


def create_process_value_card(parent, tag, column, row):
    card = ctk.CTkFrame(
        parent,
        corner_radius=10,
        fg_color=COLOR_CARD,
        border_width=2,
        border_color=COLOR_CARD_BORDER,
    )
    card.grid(row=row, column=column, padx=8, pady=6, sticky="nsew")
    parent.grid_columnconfigure(column, weight=1)

    ctk.CTkLabel(
        card,
        text=tag.name,
        font=("Arial", 12, "bold"),
        text_color="#dbeafe",
    ).pack(pady=(11, 2))
    value_label = ctk.CTkLabel(
        card,
        text="---",
        font=("Arial", 24, "bold"),
        text_color=COLOR_MUTED,
    )
    value_label.pack(pady=(2, 0))
    ctk.CTkLabel(
        card,
        text="UNIT: —",
        font=("Arial", 10, "bold"),
        text_color=COLOR_MUTED,
    ).pack(pady=(0, 3))
    metadata = create_runtime_metadata(card, tag.address)

    return {
        "frame": card,
        "value": value_label,
        **metadata,
    }


def create_runtime_metadata(card, address):
    quality_label = ctk.CTkLabel(
        card,
        text="QUALITY: BAD",
        font=("Arial", 10, "bold"),
        text_color=COLOR_RED,
    )
    quality_label.pack(pady=(1, 0))
    source_label = ctk.CTkLabel(
        card,
        text="SOURCE: —",
        font=("Arial", 9, "bold"),
        text_color=COLOR_MUTED,
    )
    source_label.pack(pady=0)
    updated_label = ctk.CTkLabel(
        card,
        text="LAST: NEVER",
        font=("Arial", 9),
        text_color=COLOR_MUTED,
    )
    updated_label.pack(pady=0)
    ctk.CTkLabel(
        card,
        text=f"ADDRESS: {address}",
        font=("Arial", 9),
        text_color=COLOR_MUTED,
    ).pack(pady=(0, 7))

    return {
        "quality": quality_label,
        "source": source_label,
        "updated": updated_label,
    }


def style_card(value_label, border_color):
    card = getattr(value_label, "card_frame", None)
    if card is not None:
        card.configure(border_color=border_color)


def refresh_dashboard(app):
    update_dashboard(app)
    app.app.after(
        DASHBOARD_REFRESH_MS,
        lambda: refresh_dashboard(app),
    )


def refresh_dashboard_tag_cards(app):
    dashboard_tags = get_dashboard_tags(app)
    signature = tuple(
        (tag.name, tag.data_type, tag.address)
        for tag in dashboard_tags
    )
    if signature == app.dashboard_tag_signature:
        return dashboard_tags

    for frame in (app.dashboard_digital_frame, app.dashboard_numeric_frame):
        for widget in frame.winfo_children():
            widget.destroy()

    app.dashboard_tag_cards.clear()
    app.dashboard_tag_signature = signature

    bool_tags = [tag for tag in dashboard_tags if tag.data_type == "BOOL"]
    numeric_tags = [
        tag for tag in dashboard_tags if tag.data_type in ("INT", "REAL")
    ]

    if not bool_tags:
        create_empty_section_label(
            app.dashboard_digital_frame,
            "No BOOL tags enabled for Dashboard",
        )
    for index, tag in enumerate(bool_tags):
        row, column = divmod(index, DIGITAL_COLUMNS)
        app.dashboard_tag_cards[tag.name] = create_digital_card(
            app.dashboard_digital_frame,
            tag,
            column,
            row,
        )

    if not numeric_tags:
        create_empty_section_label(
            app.dashboard_numeric_frame,
            "No INT/REAL tags enabled for Dashboard",
        )
    for index, tag in enumerate(numeric_tags):
        row, column = divmod(index, NUMERIC_COLUMNS)
        app.dashboard_tag_cards[tag.name] = create_process_value_card(
            app.dashboard_numeric_frame,
            tag,
            column,
            row,
        )

    return dashboard_tags


def create_empty_section_label(parent, text):
    ctk.CTkLabel(
        parent,
        text=text,
        text_color=COLOR_MUTED,
        anchor="w",
    ).grid(row=0, column=0, padx=8, pady=8, sticky="w")


def update_dashboard(app, last_message=None):
    if not hasattr(app, "card_alarm"):
        return

    pid_running = getattr(app, "pid_running", False)
    app.card_pid.configure(
        text="ON" if pid_running else "OFF",
        text_color=COLOR_GREEN if pid_running else COLOR_MUTED,
    )
    style_card(app.card_pid, COLOR_GREEN if pid_running else COLOR_CARD_BORDER)

    active_alarms = sum(
        1 for alarm in getattr(app, "alarms", [])
        if alarm.get("active", False)
    )
    unacknowledged = sum(
        1 for alarm in getattr(app, "alarms", [])
        if alarm.get("active", False) and not alarm.get("ack", False)
    )
    if unacknowledged:
        alarm_text = f"{unacknowledged} UNACK"
        alarm_color = COLOR_RED
    elif active_alarms:
        alarm_text = f"{active_alarms} ACTIVE"
        alarm_color = COLOR_AMBER
    else:
        alarm_text = "NORMAL"
        alarm_color = COLOR_GREEN
    app.card_alarm.configure(text=alarm_text, text_color=alarm_color)
    style_card(app.card_alarm, alarm_color)

    for tag in refresh_dashboard_tag_cards(app):
        card = app.dashboard_tag_cards[tag.name]
        runtime = app.tag_runtime.get(tag.name)
        update_runtime_card(card, tag.data_type, runtime)

    if last_message:
        record_dashboard_event(app, last_message)


def update_runtime_card(card, data_type, runtime):
    valid = runtime is not None and runtime.valid
    source = runtime_source_name(runtime)
    updated_at = runtime_timestamp(runtime)

    if valid and data_type == "BOOL":
        state = bool(runtime.value)
        card["value"].configure(
            text="● ON" if state else "● OFF",
            text_color=COLOR_GREEN if state else "#dbeafe",
        )
    elif valid:
        card["value"].configure(
            text=str(runtime.value),
            text_color=COLOR_CYAN,
        )
    else:
        card["value"].configure(
            text="● ---" if data_type == "BOOL" else "---",
            text_color=COLOR_RED,
        )

    card["quality"].configure(
        text="QUALITY: GOOD" if valid else "QUALITY: BAD",
        text_color=COLOR_GREEN if valid else COLOR_RED,
    )

    if source == "SIMULATION":
        source_color = COLOR_AMBER
    elif source == "PLC":
        source_color = COLOR_CYAN
    else:
        source_color = COLOR_MUTED
    card["source"].configure(
        text=f"SOURCE: {source}",
        text_color=source_color,
    )
    card["updated"].configure(
        text=f"LAST: {updated_at}",
        text_color=COLOR_MUTED,
    )

    if not valid:
        border_color = COLOR_RED
    elif source == "SIMULATION":
        border_color = COLOR_AMBER
    else:
        border_color = "#0e7490"
    card["frame"].configure(border_color=border_color)


def runtime_source_name(runtime):
    if runtime is None or runtime.source is None:
        return "—"
    return str(getattr(runtime.source, "value", runtime.source)).upper()


def runtime_timestamp(runtime):
    if runtime is None or runtime.updated_at is None:
        return "NEVER"
    try:
        return time.strftime("%H:%M:%S", time.localtime(runtime.updated_at))
    except (OverflowError, OSError, TypeError, ValueError):
        return "UNKNOWN"


def record_dashboard_event(app, message):
    message = str(message).strip()
    if not message:
        return

    if not hasattr(app, "dashboard_events"):
        app.dashboard_events = []

    app.dashboard_events.append((time.strftime("%H:%M:%S"), message))
    app.dashboard_events = app.dashboard_events[-EVENT_LIMIT:]
    render_dashboard_events(app)


def clear_dashboard_events(app):
    app.dashboard_events = []
    render_dashboard_events(app)


def render_dashboard_events(app):
    if not hasattr(app, "dashboard_event_log"):
        return

    app.dashboard_event_log.configure(state="normal")
    app.dashboard_event_log.delete("1.0", "end")
    if not app.dashboard_events:
        app.dashboard_event_log.insert("end", "--:--:--  No runtime events\n")
    else:
        for timestamp, message in app.dashboard_events:
            app.dashboard_event_log.insert(
                "end",
                f"{timestamp}  {message}\n",
            )
    app.dashboard_event_log.configure(state="disabled")
    app.dashboard_event_log.see("end")
