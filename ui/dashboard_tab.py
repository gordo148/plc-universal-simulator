import customtkinter as ctk

from ui.tag_manager import get_dashboard_tags


DASHBOARD_REFRESH_MS = 500
TAG_COLUMNS = 4
COLOR_DASHBOARD = "#0f1720"
COLOR_CARD = "#182431"
COLOR_CARD_BORDER = "#334155"
COLOR_MUTED = "#8fa3b8"
COLOR_CYAN = "#22d3ee"
COLOR_GREEN = "#22c55e"
COLOR_RED = "#ef4444"
COLOR_AMBER = "#f59e0b"


def create_dashboard_tab(app):
    app.dashboard_frame = ctk.CTkFrame(
        app.tab_dashboard,
        fg_color=COLOR_DASHBOARD,
        corner_radius=10,
    )
    app.dashboard_frame.pack(fill="both", expand=True, padx=20, pady=20)

    title = ctk.CTkLabel(
        app.dashboard_frame,
        text="OPERATIONS OVERVIEW",
        font=("Arial", 26, "bold"),
        text_color="#dbeafe",
    )
    title.pack(pady=(18, 2))

    ctk.CTkLabel(
        app.dashboard_frame,
        text="LIVE PROCESS STATUS  •  RUNTIME TAG MONITOR",
        font=("Arial", 11, "bold"),
        text_color=COLOR_MUTED,
    ).pack(pady=(0, 12))

    system_frame = ctk.CTkFrame(app.dashboard_frame, fg_color="transparent")
    system_frame.pack(fill="x", padx=20, pady=(10, 5))

    app.card_connection = create_card(
        system_frame, "COMMUNICATION", "● OFFLINE", COLOR_RED, 0,
        accent=COLOR_RED,
    )
    app.card_alarm = create_card(
        system_frame, "ALARMS", "NORMAL", COLOR_GREEN, 1,
        accent=COLOR_GREEN,
    )
    app.card_pid = create_card(
        system_frame, "PID CONTROLLER", "OFF", COLOR_MUTED, 2,
    )
    app.card_brand = create_card(
        system_frame, "PLC PLATFORM", "Siemens", "white", 3,
    )
    app.card_ip = create_card(
        system_frame, "TARGET IP", "192.168.1.10", "white", 4,
    )

    activity_frame = ctk.CTkFrame(app.dashboard_frame, fg_color="transparent")
    activity_frame.pack(fill="x", padx=20, pady=5)
    app.card_last = create_card(
        activity_frame,
        "EVENT LOG",
        "Waiting for activity...",
        COLOR_MUTED,
        0,
        accent="#3b82f6",
    )

    ctk.CTkLabel(
        app.dashboard_frame,
        text="PROCESS TAGS",
        font=("Arial", 20, "bold"),
        text_color="#dbeafe",
    ).pack(anchor="w", padx=25, pady=(15, 5))

    app.dashboard_tags_frame = ctk.CTkScrollableFrame(
        app.dashboard_frame,
        fg_color="#111c27",
        corner_radius=10,
    )
    app.dashboard_tags_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
    app.dashboard_tag_cards = {}
    app.dashboard_tag_signature = None

    update_dashboard(app)
    app.app.after(
        DASHBOARD_REFRESH_MS,
        lambda: refresh_dashboard(app),
    )


def create_card(
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
    card.grid(row=row, column=column, padx=8, pady=8, sticky="nsew")

    parent.grid_columnconfigure(column, weight=1)

    ctk.CTkLabel(
        card,
        text=title,
        font=("Arial", 12, "bold"),
        text_color=COLOR_MUTED,
    ).pack(pady=(14, 3))

    value_label = ctk.CTkLabel(
        card,
        text=value,
        font=("Arial", 22, "bold"),
        text_color=color,
    )
    value_label.pack(pady=(3, 4 if subtitle else 14))

    if subtitle:
        ctk.CTkLabel(
            card,
            text=subtitle,
            font=("Arial", 10),
            text_color=COLOR_MUTED,
        ).pack(pady=(0, 10))

    value_label.card_frame = card

    return value_label


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

    for widget in app.dashboard_tags_frame.winfo_children():
        widget.destroy()

    app.dashboard_tag_cards.clear()
    app.dashboard_tag_signature = signature

    if not dashboard_tags:
        ctk.CTkLabel(
            app.dashboard_tags_frame,
            text="Nenhuma tag habilitada para o Dashboard",
            text_color="gray",
        ).grid(row=0, column=0, padx=15, pady=20, sticky="w")
        return dashboard_tags

    for index, tag in enumerate(dashboard_tags):
        row, column = divmod(index, TAG_COLUMNS)
        initial_value = "● ---" if tag.data_type == "BOOL" else "---"
        label = create_card(
            app.dashboard_tags_frame,
            tag.name.upper(),
            initial_value,
            COLOR_MUTED,
            column,
            row,
            subtitle=f"{tag.data_type}  •  {tag.address}",
        )
        app.dashboard_tag_cards[tag.name] = label

    return dashboard_tags


def update_dashboard(app, last_message=None):
    if not hasattr(app, "card_connection"):
        return

    connected = app.plc_service.is_connected()
    app.card_connection.configure(
        text="● ONLINE" if connected else "● OFFLINE",
        text_color=COLOR_GREEN if connected else COLOR_RED,
    )
    style_card(app.card_connection, COLOR_GREEN if connected else COLOR_RED)

    app.card_brand.configure(text=app.brand_menu.get())
    app.card_ip.configure(text=app.ip_entry.get())

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
        label = app.dashboard_tag_cards[tag.name]
        runtime = app.tag_runtime.get(tag.name)

        if runtime is None or not runtime.valid:
            text = "● ---" if tag.data_type == "BOOL" else "---"
            color = COLOR_MUTED
            border_color = COLOR_CARD_BORDER
        elif tag.data_type == "BOOL":
            state = bool(runtime.value)
            text = "● ON" if state else "● OFF"
            color = COLOR_GREEN if state else COLOR_MUTED
            border_color = COLOR_GREEN if state else COLOR_CARD_BORDER
        else:
            text = str(runtime.value)
            color = COLOR_CYAN
            border_color = "#0e7490"

        label.configure(text=text, text_color=color)
        style_card(label, border_color)

    if last_message:
        app.card_last.configure(text=last_message)
