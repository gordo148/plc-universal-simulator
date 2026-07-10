import os

import customtkinter as ctk

SCHNEIDER_MODELS = {
    "M221": {"coil_start": 0, "reg_start": 0, "description": "M221 / Machine Expert Basic"},
    "M241": {"coil_start": 0, "reg_start": 0, "description": "M241 / Machine Expert"},
    "M340": {"coil_start": 1000, "reg_start": 1000, "description": "M340 / Control Expert"},
    "M580": {"coil_start": 1000, "reg_start": 1000, "description": "M580 / Control Expert"},
}

STATUS_REFRESH_MS = 500
COLOR_PANEL = "#16212d"
COLOR_PANEL_ALT = "#1d2b38"
COLOR_BORDER = "#34495e"
COLOR_TEXT_MUTED = "#91a4b7"
COLOR_ONLINE = "#21c55d"
COLOR_OFFLINE = "#ef4444"
COLOR_WARNING = "#f59e0b"


def create_header(app):
    app.top_status_bar = ctk.CTkFrame(
        app.app,
        height=48,
        corner_radius=8,
        fg_color=COLOR_PANEL,
        border_width=1,
        border_color=COLOR_BORDER,
    )
    app.top_status_bar.pack(fill="x", padx=10, pady=(10, 4))

    app.top_project = create_status_item(
        app.top_status_bar, "PROJECT", "Novo Projeto", 0
    )
    app.top_brand = create_status_item(
        app.top_status_bar, "PLC", "Siemens", 1
    )
    app.top_ip = create_status_item(
        app.top_status_bar, "IP ADDRESS", "192.168.1.10", 2
    )
    app.top_mode = create_status_item(
        app.top_status_bar, "MODE", "● OFFLINE", 3, COLOR_OFFLINE
    )
    app.top_alarms = create_status_item(
        app.top_status_bar, "ALARMS", "NORMAL", 4, COLOR_ONLINE
    )

    app.header = ctk.CTkFrame(
        app.app,
        corner_radius=8,
        fg_color=COLOR_PANEL_ALT,
        border_width=1,
        border_color=COLOR_BORDER,
    )
    app.header.pack(fill="x", padx=10, pady=(4, 4))

    ctk.CTkLabel(app.header, text="Marca").grid(row=0, column=0, padx=5)
    app.brand_menu = ctk.CTkOptionMenu(
        app.header,
        values=[
            "Siemens",
            "Schneider",
            "Modbus TCP",
            "Rockwell",
            "Omron",
            "Simulator",
        ],
        command=app.update_brand
    )
    app.brand_menu.set("Siemens")
    app.brand_menu.grid(row=0, column=1, padx=5)

    app.ip_label = ctk.CTkLabel(app.header, text="IP")
    app.ip_label.grid(row=0, column=2, padx=5)
    app.ip_entry = ctk.CTkEntry(app.header, width=140)
    app.ip_entry.insert(0, "192.168.1.10")
    app.ip_entry.grid(row=0, column=3, padx=5)

    ctk.CTkButton(app.header, text="Ligar", command=app.connect, width=80).grid(row=0, column=4, padx=4)
    ctk.CTkButton(app.header, text="Desligar", command=app.disconnect, width=80).grid(row=0, column=5, padx=4)
    ctk.CTkButton(app.header, text="Gerar", command=app.generate_signals, width=80).grid(row=0, column=6, padx=4)
    ctk.CTkButton(app.header, text="Reset", command=app.reset_all, width=80).grid(row=0, column=7, padx=4)
    ctk.CTkButton(app.header, text="Novo", command=app.new_project, width=70).grid(row=0, column=8, padx=4)
    ctk.CTkButton(app.header, text="Guardar", command=app.save_project, width=75).grid(row=0, column=9, padx=4)
    ctk.CTkButton(app.header, text="Guardar Como", command=app.save_project_as, width=105).grid(row=0, column=10, padx=4)
    ctk.CTkButton(app.header, text="Abrir", command=app.open_project, width=70).grid(row=0, column=11, padx=4)

    app.status_label = ctk.CTkLabel(
        app.header,
        text="● DESLIGADO",
        text_color="red",
        font=("Arial", 14, "bold")
    )
    app.status_label.grid(row=0, column=12, padx=15)

    app.brand_frame = ctk.CTkFrame(app.header)
    app.brand_frame.grid(row=1, column=0, columnspan=13, sticky="ew", padx=5, pady=10)

    app.utility_frame = ctk.CTkFrame(app.header, fg_color="transparent")
    app.utility_frame.grid(row=2, column=0, columnspan=13, sticky="ew", padx=5, pady=(0, 8))
    ctk.CTkLabel(app.utility_frame, text="Projetos recentes").pack(side="left", padx=5)
    app.recent_project_menu = ctk.CTkOptionMenu(
        app.utility_frame,
        values=["Nenhum projeto recente"],
        width=380,
    )
    app.recent_project_menu.pack(side="left", padx=5)
    ctk.CTkButton(
        app.utility_frame,
        text="Abrir recente",
        command=app.open_recent_project,
        width=100,
    ).pack(side="left", padx=4)
    ctk.CTkButton(
        app.utility_frame,
        text="About",
        command=app.show_about,
        width=70,
    ).pack(side="right", padx=4)

    app.alarm_banner = ctk.CTkLabel(
        app.app,
        text="",
        height=34,
        corner_radius=7,
        fg_color="#7f1d1d",
        text_color="#fecaca",
        font=("Arial", 13, "bold"),
    )

    app.create_siemens_options = lambda: create_siemens_options(app)
    app.create_schneider_options = lambda: create_schneider_options(app)
    app.create_modbus_options = lambda: create_modbus_options(app)
    app.create_rockwell_options = lambda: create_rockwell_options(app)
    app.create_omron_options = lambda: create_omron_options(app)
    app.create_simulator_options = lambda: create_simulator_options(app)
    app.create_siemens_options()
    update_top_status_bar(app)
    app.schedule_job(
        STATUS_REFRESH_MS,
        lambda: refresh_top_status_bar(app),
    )


def create_status_item(parent, title, value, column, color="white"):
    item = ctk.CTkFrame(parent, fg_color="transparent")
    item.grid(row=0, column=column, padx=18, pady=7, sticky="ew")
    parent.grid_columnconfigure(column, weight=1)

    ctk.CTkLabel(
        item,
        text=title,
        text_color=COLOR_TEXT_MUTED,
        font=("Arial", 10, "bold"),
        anchor="w",
    ).pack(fill="x")
    value_label = ctk.CTkLabel(
        item,
        text=value,
        text_color=color,
        font=("Arial", 14, "bold"),
        anchor="w",
    )
    value_label.pack(fill="x")
    return value_label


def refresh_top_status_bar(app):
    if getattr(app, "is_closing", False):
        return
    update_top_status_bar(app)
    app.schedule_job(
        STATUS_REFRESH_MS,
        lambda: refresh_top_status_bar(app),
    )


def update_top_status_bar(app):
    if not hasattr(app, "top_status_bar") or not hasattr(app, "brand_menu"):
        return

    project_path = getattr(app, "project_path", None)
    project_name = (
        os.path.splitext(os.path.basename(project_path))[0]
        if project_path else "Novo Projeto"
    )
    app.top_project.configure(text=project_name)
    app.top_brand.configure(text=app.brand_menu.get())
    if app.brand_menu.get() == "Simulator":
        app.top_ip.configure(text="INTERNAL")
    else:
        app.top_ip.configure(text=app.ip_entry.get() or "—")

    connected = app.plc_service.is_connected()
    simulator_online = connected and app.brand_menu.get() == "Simulator"
    app.top_mode.configure(
        text=(
            "● ONLINE SIM"
            if simulator_online
            else "● ONLINE" if connected else "● OFFLINE"
        ),
        text_color=COLOR_ONLINE if connected else COLOR_OFFLINE,
    )

    alarms = getattr(app, "alarms", [])
    active = [alarm for alarm in alarms if alarm.get("active", False)]
    unacknowledged = [
        alarm for alarm in active if not alarm.get("ack", False)
    ]

    if unacknowledged:
        app.top_alarms.configure(
            text=f"{len(unacknowledged)} UNACK / {len(active)} ACTIVE",
            text_color=COLOR_OFFLINE,
        )
        details = "  |  ".join(
            f"{alarm.get('source', '?')} {alarm.get('type', 'ALARM')}"
            for alarm in unacknowledged[:3]
        )
        if len(unacknowledged) > 3:
            details += f"  |  +{len(unacknowledged) - 3} MORE"
        app.alarm_banner.configure(
            text=f"⚠ UNACKNOWLEDGED ALARM — {details}",
            fg_color="#7f1d1d",
            text_color="#fecaca",
        )
        show_alarm_banner(app)
    elif active:
        app.top_alarms.configure(
            text=f"{len(active)} ACTIVE / ACK",
            text_color=COLOR_WARNING,
        )
        hide_alarm_banner(app)
    else:
        app.top_alarms.configure(text="NORMAL", text_color=COLOR_ONLINE)
        hide_alarm_banner(app)


def show_alarm_banner(app):
    if app.alarm_banner.winfo_manager() == "pack":
        return

    options = {
        "fill": "x",
        "padx": 10,
        "pady": (0, 4),
    }
    if hasattr(app, "tabs"):
        options["before"] = app.tabs
    app.alarm_banner.pack(**options)


def hide_alarm_banner(app):
    if app.alarm_banner.winfo_manager() == "pack":
        app.alarm_banner.pack_forget()


def clear_brand_frame(app):
    _set_ip_visibility(app, True)
    for widget in app.brand_frame.winfo_children():
        widget.destroy()


def _set_ip_visibility(app, visible):
    if visible:
        app.ip_label.grid()
        app.ip_entry.grid()
    else:
        app.ip_label.grid_remove()
        app.ip_entry.grid_remove()


def create_siemens_options(app):
    clear_brand_frame(app)

    ctk.CTkLabel(app.brand_frame, text="Rack").grid(row=0, column=0, padx=5)
    app.rack_entry = ctk.CTkEntry(app.brand_frame, width=70)
    app.rack_entry.insert(0, "0")
    app.rack_entry.grid(row=0, column=1, padx=5)

    ctk.CTkLabel(app.brand_frame, text="Slot").grid(row=0, column=2, padx=5)
    app.slot_entry = ctk.CTkEntry(app.brand_frame, width=70)
    app.slot_entry.insert(0, "1")
    app.slot_entry.grid(row=0, column=3, padx=5)

    ctk.CTkLabel(app.brand_frame, text="DB").grid(row=0, column=4, padx=5)
    app.db_entry = ctk.CTkEntry(app.brand_frame, width=80)
    app.db_entry.insert(0, "100")
    app.db_entry.grid(row=0, column=5, padx=5)

    ctk.CTkLabel(app.brand_frame, text="Siemens: DBX / DBW", text_color="gray").grid(row=0, column=6, padx=20)


def create_schneider_options(app):
    clear_brand_frame(app)

    ctk.CTkLabel(app.brand_frame, text="Modelo").grid(row=0, column=0, padx=5)
    app.schneider_model_menu = ctk.CTkOptionMenu(
        app.brand_frame,
        values=list(SCHNEIDER_MODELS.keys()),
        command=app.update_schneider_model
    )
    app.schneider_model_menu.set("M221")
    app.schneider_model_menu.grid(row=0, column=1, padx=5)

    ctk.CTkLabel(app.brand_frame, text="Porta").grid(row=0, column=2, padx=5)
    app.port_entry = ctk.CTkEntry(app.brand_frame, width=80)
    app.port_entry.insert(0, "502")
    app.port_entry.grid(row=0, column=3, padx=5)

    ctk.CTkLabel(app.brand_frame, text="Slave ID").grid(row=0, column=4, padx=5)
    app.slave_entry = ctk.CTkEntry(app.brand_frame, width=80)
    app.slave_entry.insert(0, "1")
    app.slave_entry.grid(row=0, column=5, padx=5)

    ctk.CTkLabel(app.brand_frame, text="%M inicial").grid(row=0, column=6, padx=5)
    app.coil_start_entry = ctk.CTkEntry(app.brand_frame, width=90)
    app.coil_start_entry.insert(0, "0")
    app.coil_start_entry.grid(row=0, column=7, padx=5)

    ctk.CTkLabel(app.brand_frame, text="%MW inicial").grid(row=0, column=8, padx=5)
    app.reg_start_entry = ctk.CTkEntry(app.brand_frame, width=90)
    app.reg_start_entry.insert(0, "0")
    app.reg_start_entry.grid(row=0, column=9, padx=5)

    app.schneider_info = ctk.CTkLabel(
        app.brand_frame,
        text=SCHNEIDER_MODELS["M221"]["description"],
        text_color="gray"
    )
    app.schneider_info.grid(row=0, column=10, padx=20)


def create_modbus_options(app):
    clear_brand_frame(app)

    ctk.CTkLabel(app.brand_frame, text="Porta").grid(
        row=0,
        column=0,
        padx=5,
    )
    app.port_entry = ctk.CTkEntry(app.brand_frame, width=80)
    app.port_entry.insert(0, "502")
    app.port_entry.grid(row=0, column=1, padx=5)

    ctk.CTkLabel(app.brand_frame, text="Slave ID").grid(
        row=0,
        column=2,
        padx=5,
    )
    app.slave_entry = ctk.CTkEntry(app.brand_frame, width=80)
    app.slave_entry.insert(0, "1")
    app.slave_entry.grid(row=0, column=3, padx=5)

    ctk.CTkLabel(
        app.brand_frame,
        text="Modbus TCP: coils / holding registers",
        text_color="gray",
    ).grid(row=0, column=4, padx=20)


def create_rockwell_options(app):
    clear_brand_frame(app)
    ctk.CTkLabel(
        app.brand_frame,
        text="Rockwell EtherNet/IP — symbolic tags",
        text_color="gray",
    ).grid(row=0, column=0, padx=20)


def create_omron_options(app):
    clear_brand_frame(app)

    fields = (
        ("FINS Port", "port_entry", "9600"),
        ("Destination Node", "destination_node_entry", "0"),
        ("Source Node", "source_node_entry", "1"),
    )
    for index, (label, attribute, default) in enumerate(fields):
        column = index * 2
        ctk.CTkLabel(app.brand_frame, text=label).grid(
            row=0,
            column=column,
            padx=5,
        )
        entry = ctk.CTkEntry(app.brand_frame, width=90)
        entry.insert(0, default)
        entry.grid(row=0, column=column + 1, padx=5)
        setattr(app, attribute, entry)

    ctk.CTkLabel(
        app.brand_frame,
        text="Omron FINS/UDP — CIO bits / DM words",
        text_color="gray",
    ).grid(row=0, column=6, padx=20)


def create_simulator_options(app):
    clear_brand_frame(app)
    _set_ip_visibility(app, False)
    ctk.CTkLabel(
        app.brand_frame,
        text="Internal PLC Simulator — no network required",
        text_color="gray",
    ).grid(row=0, column=0, padx=20)
