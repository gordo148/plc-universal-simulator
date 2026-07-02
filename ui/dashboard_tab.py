import customtkinter as ctk

from ui.tag_manager import get_input_analog_tags, get_input_bool_tags


def create_dashboard_tab(app):
    app.dashboard_frame = ctk.CTkFrame(app.tab_dashboard)
    app.dashboard_frame.pack(fill="both", expand=True, padx=20, pady=20)

    title = ctk.CTkLabel(
        app.dashboard_frame,
        text="PLC Simulator Dashboard",
        font=("Arial", 28, "bold")
    )
    title.pack(pady=20)

    cards_frame = ctk.CTkFrame(app.dashboard_frame)
    cards_frame.pack(fill="x", padx=20, pady=20)

    app.card_connection = create_card(cards_frame, "Comunicação", "● Offline", "red", 0)
    app.card_brand = create_card(cards_frame, "PLC", "Siemens", "white", 1)
    app.card_ip = create_card(cards_frame, "IP", "192.168.1.10", "white", 2)
    app.card_pid = create_card(cards_frame, "PID", "OFF", "gray", 3)

    counters_frame = ctk.CTkFrame(app.dashboard_frame)
    counters_frame.pack(fill="x", padx=20, pady=20)

    app.card_di = create_card(counters_frame, "Digitais ON", "0 / 0", "lime", 0)
    app.card_ai = create_card(counters_frame, "Analógicas", "0", "cyan", 1)
    app.card_last = create_card(counters_frame, "Último estado", "Aguardando...", "gray", 2)


def create_card(parent, title, value, color, column):
    card = ctk.CTkFrame(parent, corner_radius=15)
    card.grid(row=0, column=column, padx=12, pady=12, sticky="nsew")

    parent.grid_columnconfigure(column, weight=1)

    title_label = ctk.CTkLabel(
        card,
        text=title,
        font=("Arial", 15),
        text_color="gray"
    )
    title_label.pack(pady=(18, 5))

    value_label = ctk.CTkLabel(
        card,
        text=value,
        font=("Arial", 24, "bold"),
        text_color=color
    )
    value_label.pack(pady=(5, 18))

    return value_label


def update_dashboard(app, last_message=None):
    if not hasattr(app, "card_connection"):
        return

    brand = app.brand_menu.get()
    ip = app.ip_entry.get()

    connected = app.plc_service.is_connected()

    if connected:
        app.card_connection.configure(text="● Online", text_color="lime")
    else:
        app.card_connection.configure(text="● Offline", text_color="red")

    app.card_brand.configure(text=brand)
    app.card_ip.configure(text=ip)

    if getattr(app, "pid_running", False):
        app.card_pid.configure(text="ON", text_color="lime")
    else:
        app.card_pid.configure(text="OFF", text_color="gray")

    digital_tags = get_input_bool_tags(app)
    analog_tags = get_input_analog_tags(app)
    total_di = len(digital_tags)
    on_di = sum(
        1 for tag in digital_tags
        if bool(app.tag_runtime.get_value(tag.name, False))
    )

    app.card_di.configure(text=f"{on_di} / {total_di}")
    app.card_ai.configure(text=str(len(analog_tags)))

    if last_message:
        app.card_last.configure(text=last_message)
