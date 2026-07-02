import customtkinter as ctk

from ui.tag_manager import get_dashboard_tags


DASHBOARD_REFRESH_MS = 500
TAG_COLUMNS = 4


def create_dashboard_tab(app):
    app.dashboard_frame = ctk.CTkFrame(app.tab_dashboard)
    app.dashboard_frame.pack(fill="both", expand=True, padx=20, pady=20)

    title = ctk.CTkLabel(
        app.dashboard_frame,
        text="PLC Simulator Dashboard",
        font=("Arial", 28, "bold")
    )
    title.pack(pady=20)

    system_frame = ctk.CTkFrame(app.dashboard_frame)
    system_frame.pack(fill="x", padx=20, pady=(10, 5))

    app.card_connection = create_card(system_frame, "Comunicação", "● Offline", "red", 0)
    app.card_alarm = create_card(system_frame, "Alarmes", "0 ativos", "lime", 1)
    app.card_pid = create_card(system_frame, "PID", "OFF", "gray", 2)
    app.card_brand = create_card(system_frame, "PLC", "Siemens", "white", 3)
    app.card_ip = create_card(system_frame, "IP", "192.168.1.10", "white", 4)

    activity_frame = ctk.CTkFrame(app.dashboard_frame)
    activity_frame.pack(fill="x", padx=20, pady=5)
    app.card_last = create_card(
        activity_frame,
        "Último estado",
        "Aguardando...",
        "gray",
        0,
    )

    ctk.CTkLabel(
        app.dashboard_frame,
        text="Tags",
        font=("Arial", 20, "bold"),
    ).pack(anchor="w", padx=25, pady=(15, 5))

    app.dashboard_tags_frame = ctk.CTkScrollableFrame(app.dashboard_frame)
    app.dashboard_tags_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
    app.dashboard_tag_cards = {}
    app.dashboard_tag_signature = None

    update_dashboard(app)
    app.app.after(
        DASHBOARD_REFRESH_MS,
        lambda: refresh_dashboard(app),
    )


def create_card(parent, title, value, color, column, row=0):
    card = ctk.CTkFrame(parent, corner_radius=15)
    card.grid(row=row, column=column, padx=12, pady=12, sticky="nsew")

    parent.grid_columnconfigure(column, weight=1)

    ctk.CTkLabel(
        card,
        text=title,
        font=("Arial", 15),
        text_color="gray"
    ).pack(pady=(18, 5))

    value_label = ctk.CTkLabel(
        card,
        text=value,
        font=("Arial", 24, "bold"),
        text_color=color
    )
    value_label.pack(pady=(5, 18))

    return value_label


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
            tag.name,
            initial_value,
            "gray",
            column,
            row,
        )
        app.dashboard_tag_cards[tag.name] = label

    return dashboard_tags


def update_dashboard(app, last_message=None):
    if not hasattr(app, "card_connection"):
        return

    connected = app.plc_service.is_connected()
    app.card_connection.configure(
        text="● Online" if connected else "● Offline",
        text_color="lime" if connected else "red",
    )

    app.card_brand.configure(text=app.brand_menu.get())
    app.card_ip.configure(text=app.ip_entry.get())

    pid_running = getattr(app, "pid_running", False)
    app.card_pid.configure(
        text="ON" if pid_running else "OFF",
        text_color="lime" if pid_running else "gray",
    )

    active_alarms = sum(
        1 for alarm in getattr(app, "alarms", [])
        if alarm.get("active", False)
    )
    unacknowledged = sum(
        1 for alarm in getattr(app, "alarms", [])
        if alarm.get("active", False) and not alarm.get("ack", False)
    )
    if unacknowledged:
        alarm_text = f"{active_alarms} ativos / {unacknowledged} ACK"
        alarm_color = "red"
    elif active_alarms:
        alarm_text = f"{active_alarms} ativos"
        alarm_color = "orange"
    else:
        alarm_text = "0 ativos"
        alarm_color = "lime"
    app.card_alarm.configure(text=alarm_text, text_color=alarm_color)

    for tag in refresh_dashboard_tag_cards(app):
        label = app.dashboard_tag_cards[tag.name]
        runtime = app.tag_runtime.get(tag.name)

        if runtime is None or not runtime.valid:
            text = "● ---" if tag.data_type == "BOOL" else "---"
            color = "gray"
        elif tag.data_type == "BOOL":
            state = bool(runtime.value)
            text = "● ON" if state else "● OFF"
            color = "lime" if state else "gray"
        else:
            text = str(runtime.value)
            color = "cyan"

        label.configure(text=text, text_color=color)

    if last_message:
        app.card_last.configure(text=last_message)
