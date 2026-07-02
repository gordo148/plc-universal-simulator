import time
import customtkinter as ctk


def create_alarm_tab(app):
    app.alarms = []
    app.alarm_rows = []

    frame = ctk.CTkFrame(app.tab_alarms)
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    controls = ctk.CTkFrame(frame)
    controls.pack(fill="x", padx=10, pady=10)

    ctk.CTkLabel(controls, text="Variável").pack(side="left", padx=5)

    app.alarm_source_menu = ctk.CTkOptionMenu(
        controls,
        values=["AI_01"]
    )
    app.alarm_source_menu.pack(side="left", padx=5)

    ctk.CTkLabel(controls, text="Tipo").pack(side="left", padx=5)

    app.alarm_type_menu = ctk.CTkOptionMenu(
        controls,
        values=["HIGH HIGH", "HIGH", "LOW", "LOW LOW"]
    )
    app.alarm_type_menu.set("HIGH")
    app.alarm_type_menu.pack(side="left", padx=5)

    ctk.CTkLabel(controls, text="Limite").pack(side="left", padx=5)

    app.alarm_limit_entry = ctk.CTkEntry(controls, width=100)
    app.alarm_limit_entry.insert(0, "20000")
    app.alarm_limit_entry.pack(side="left", padx=5)

    ctk.CTkButton(
        controls,
        text="Adicionar Alarme",
        command=lambda: add_alarm(app),
        width=150
    ).pack(side="left", padx=10)

    ctk.CTkButton(
        controls,
        text="Atualizar Fontes",
        command=lambda: update_alarm_sources(app),
        width=140
    ).pack(side="left", padx=10)

    app.alarm_status_label = ctk.CTkLabel(
        controls,
        text="Alarmes: 0 ativos",
        text_color="gray",
        font=("Arial", 15, "bold")
    )
    app.alarm_status_label.pack(side="left", padx=20)

    header = ctk.CTkFrame(frame)
    header.pack(fill="x", padx=10, pady=(10, 0))

    headers = ["Estado", "Variável", "Tipo", "Limite", "Valor", "Hora", "ACK", "Ação"]

    for col, text in enumerate(headers):
        ctk.CTkLabel(
            header,
            text=text,
            font=("Arial", 13, "bold"),
            width=120
        ).grid(row=0, column=col, padx=4, pady=6)

    app.alarm_table = ctk.CTkScrollableFrame(frame)
    app.alarm_table.pack(fill="both", expand=True, padx=10, pady=10)

    update_alarm_sources(app)
    start_alarm_scan(app)


def update_alarm_sources(app):
    if not hasattr(app, "alarm_source_menu"):
        return

    values = []

    for i in range(len(app.analog_widgets)):
        values.append(f"AI_{i + 1:02d}")

    values.append("PID PV")
    values.append("PID OUT")

    if not values:
        values = ["AI_01"]

    app.alarm_source_menu.configure(values=values)
    app.alarm_source_menu.set(values[0])


def add_alarm(app):
    try:
        source = app.alarm_source_menu.get()
        alarm_type = app.alarm_type_menu.get()
        limit = int(app.alarm_limit_entry.get())
    except Exception:
        app.status_label.configure(text="● ERRO ALARME", text_color="orange")
        return

    alarm = {
        "source": source,
        "type": alarm_type,
        "limit": limit,
        "active": False,
        "ack": False,
        "last_value": 0,
        "timestamp": "-"
    }

    app.alarms.append(alarm)
    create_alarm_row(app, alarm)
    update_alarm_status(app)


def create_alarm_row(app, alarm):
    row = ctk.CTkFrame(app.alarm_table)
    row.pack(fill="x", padx=5, pady=4)

    state = ctk.CTkLabel(row, text="NORMAL", text_color="lime", width=120)
    state.grid(row=0, column=0, padx=4, pady=6)

    source = ctk.CTkLabel(row, text=alarm["source"], width=120)
    source.grid(row=0, column=1, padx=4)

    alarm_type = ctk.CTkLabel(row, text=alarm["type"], width=120)
    alarm_type.grid(row=0, column=2, padx=4)

    limit = ctk.CTkLabel(row, text=str(alarm["limit"]), width=120)
    limit.grid(row=0, column=3, padx=4)

    value = ctk.CTkLabel(row, text="0", width=120)
    value.grid(row=0, column=4, padx=4)

    timestamp = ctk.CTkLabel(row, text="-", width=160)
    timestamp.grid(row=0, column=5, padx=4)

    ack = ctk.CTkLabel(row, text="NO", text_color="gray", width=80)
    ack.grid(row=0, column=6, padx=4)

    ctk.CTkButton(
        row,
        text="ACK",
        width=80,
        command=lambda a=alarm: acknowledge_alarm(app, a)
    ).grid(row=0, column=7, padx=4)

    app.alarm_rows.append({
        "alarm": alarm,
        "state": state,
        "value": value,
        "timestamp": timestamp,
        "ack": ack
    })


def acknowledge_alarm(app, alarm):
    alarm["ack"] = True
    update_alarm_table(app)


def get_alarm_value(app, source):
    try:
        if source.startswith("AI_"):
            index = int(source.split("_")[1]) - 1
            return int(app.analog_widgets[index]["live"].cget("text"))

        if source == "PID PV":
            return int(app.pid_pv_label.cget("text").replace("PV:", "").strip())

        if source == "PID OUT":
            return int(app.pid_out_label.cget("text").replace("OUT:", "").strip())

    except Exception:
        return 0

    return 0


def start_alarm_scan(app):
    scan_alarms(app)


def scan_alarms(app):
    if not hasattr(app, "alarms"):
        return

    for alarm in app.alarms:
        value = get_alarm_value(app, alarm["source"])
        alarm["last_value"] = value

        was_active = alarm["active"]

        if alarm["type"] in ["HIGH HIGH", "HIGH"]:
            alarm["active"] = value > alarm["limit"]
        else:
            alarm["active"] = value < alarm["limit"]

        if alarm["active"] and not was_active:
            alarm["timestamp"] = time.strftime("%H:%M:%S")
            alarm["ack"] = False

    update_alarm_table(app)
    update_alarm_status(app)

    app.app.after(500, lambda: scan_alarms(app))


def update_alarm_table(app):
    for row in app.alarm_rows:
        alarm = row["alarm"]

        row["value"].configure(text=str(alarm["last_value"]))
        row["timestamp"].configure(text=alarm["timestamp"])

        if alarm["active"] and not alarm["ack"]:
            row["state"].configure(text=alarm["type"], text_color=get_alarm_color(alarm["type"]))
            row["ack"].configure(text="NO", text_color="red")

        elif alarm["active"] and alarm["ack"]:
            row["state"].configure(text=f"{alarm['type']} ACK", text_color="orange")
            row["ack"].configure(text="YES", text_color="orange")

        else:
            row["state"].configure(text="NORMAL", text_color="lime")
            row["ack"].configure(text="NO", text_color="gray")


def get_alarm_color(alarm_type):
    if alarm_type == "HIGH HIGH":
        return "red"

    if alarm_type == "HIGH":
        return "orange"

    if alarm_type == "LOW":
        return "orange"

    if alarm_type == "LOW LOW":
        return "red"

    return "red"


def update_alarm_status(app):
    if not hasattr(app, "alarm_status_label"):
        return

    active_count = sum(1 for alarm in app.alarms if alarm["active"])
    unacked_count = sum(1 for alarm in app.alarms if alarm["active"] and not alarm["ack"])

    if unacked_count > 0:
        app.alarm_status_label.configure(
            text=f"Alarmes: {active_count} ativos / {unacked_count} por reconhecer",
            text_color="red"
        )
    elif active_count > 0:
        app.alarm_status_label.configure(
            text=f"Alarmes: {active_count} ativos / todos ACK",
            text_color="orange"
        )
    else:
        app.alarm_status_label.configure(
            text="Alarmes: 0 ativos",
            text_color="lime"
        )