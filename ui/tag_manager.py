import customtkinter as ctk
from core.tag_model import Tag


COL_WIDTHS = {
    "name": 180,
    "type": 90,
    "direction": 120,
    "address": 140,
    "sim": 70,
    "trend": 70,
    "alarm": 70,
    "dash": 70,
    "delete": 90,
}


def create_tag_manager_tab(app):
    if not hasattr(app, "tags"):
        app.tags = []

    frame = ctk.CTkFrame(app.tab_tags)
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    controls = ctk.CTkFrame(frame)
    controls.pack(fill="x", padx=10, pady=10)

    app.tag_name_entry = ctk.CTkEntry(controls, width=180)
    app.tag_name_entry.insert(0, "Start_Button")
    app.tag_name_entry.pack(side="left", padx=5)

    app.tag_type_menu = ctk.CTkOptionMenu(
        controls,
        values=["BOOL", "INT", "REAL"],
        width=90
    )
    app.tag_type_menu.set("BOOL")
    app.tag_type_menu.pack(side="left", padx=5)

    app.tag_direction_menu = ctk.CTkOptionMenu(
        controls,
        values=["Input", "Feedback", "Output", "Internal"],
        width=120
    )
    app.tag_direction_menu.set("Input")
    app.tag_direction_menu.pack(side="left", padx=5)

    app.tag_address_entry = ctk.CTkEntry(controls, width=140)
    app.tag_address_entry.insert(0, "DBX0.0")
    app.tag_address_entry.pack(side="left", padx=5)

    ctk.CTkButton(
        controls,
        text="Adicionar Tag",
        command=lambda: add_tag(app),
        width=130
    ).pack(side="left", padx=10)

    ctk.CTkButton(
        controls,
        text="Atualizar Sinais",
        command=lambda: app.generate_signals(),
        width=130
    ).pack(side="left", padx=5)

    header = ctk.CTkFrame(frame)
    header.pack(fill="x", padx=10, pady=(10, 0))

    create_header_cell(header, "Nome", 0, COL_WIDTHS["name"])
    create_header_cell(header, "Tipo", 1, COL_WIDTHS["type"])
    create_header_cell(header, "Direção", 2, COL_WIDTHS["direction"])
    create_header_cell(header, "Endereço", 3, COL_WIDTHS["address"])
    create_header_cell(header, "Sim", 4, COL_WIDTHS["sim"])
    create_header_cell(header, "Trend", 5, COL_WIDTHS["trend"])
    create_header_cell(header, "Alarme", 6, COL_WIDTHS["alarm"])
    create_header_cell(header, "Dash", 7, COL_WIDTHS["dash"])
    create_header_cell(header, "Ação", 8, COL_WIDTHS["delete"])

    app.tag_table = ctk.CTkScrollableFrame(frame)
    app.tag_table.pack(fill="both", expand=True, padx=10, pady=10)

    refresh_tag_table(app)


def create_header_cell(parent, text, column, width):
    ctk.CTkLabel(
        parent,
        text=text,
        font=("Arial", 13, "bold"),
        width=width,
        anchor="center"
    ).grid(row=0, column=column, padx=4, pady=6)


def add_tag(app):
    tag = Tag(
        name=app.tag_name_entry.get(),
        data_type=app.tag_type_menu.get(),
        direction=app.tag_direction_menu.get(),
        address=app.tag_address_entry.get(),
        enabled_sim=True if app.tag_direction_menu.get() == "Input" else False,
        enabled_trend=True,
        enabled_alarm=False,
        enabled_dashboard=True
    )

    app.tags.append(tag)
    refresh_tag_table(app)
    app.generate_signals()


def refresh_tag_table(app):
    for widget in app.tag_table.winfo_children():
        widget.destroy()

    for tag in app.tags:
        create_tag_row(app, tag)


def create_tag_row(app, tag):
    row = ctk.CTkFrame(app.tag_table)
    row.pack(fill="x", padx=5, pady=4)

    ctk.CTkLabel(row, text=tag.name, width=COL_WIDTHS["name"], anchor="w").grid(row=0, column=0, padx=4, pady=5)
    ctk.CTkLabel(row, text=tag.data_type, width=COL_WIDTHS["type"], anchor="center").grid(row=0, column=1, padx=4)
    ctk.CTkLabel(row, text=tag.direction, width=COL_WIDTHS["direction"], anchor="center").grid(row=0, column=2, padx=4)
    ctk.CTkLabel(row, text=tag.address, width=COL_WIDTHS["address"], anchor="center").grid(row=0, column=3, padx=4)

    sim_var = ctk.BooleanVar(value=tag.enabled_sim)
    trend_var = ctk.BooleanVar(value=tag.enabled_trend)
    alarm_var = ctk.BooleanVar(value=tag.enabled_alarm)
    dash_var = ctk.BooleanVar(value=tag.enabled_dashboard)

    ctk.CTkCheckBox(
        row,
        text="",
        variable=sim_var,
        command=lambda: set_tag_flag(app, tag, "enabled_sim", sim_var.get()),
        width=COL_WIDTHS["sim"]
    ).grid(row=0, column=4, padx=4)

    ctk.CTkCheckBox(
        row,
        text="",
        variable=trend_var,
        command=lambda: set_tag_flag(app, tag, "enabled_trend", trend_var.get()),
        width=COL_WIDTHS["trend"]
    ).grid(row=0, column=5, padx=4)

    ctk.CTkCheckBox(
        row,
        text="",
        variable=alarm_var,
        command=lambda: set_tag_flag(app, tag, "enabled_alarm", alarm_var.get()),
        width=COL_WIDTHS["alarm"]
    ).grid(row=0, column=6, padx=4)

    ctk.CTkCheckBox(
        row,
        text="",
        variable=dash_var,
        command=lambda: set_tag_flag(app, tag, "enabled_dashboard", dash_var.get()),
        width=COL_WIDTHS["dash"]
    ).grid(row=0, column=7, padx=4)

    ctk.CTkButton(
        row,
        text="Eliminar",
        width=COL_WIDTHS["delete"],
        fg_color="#8b1e1e",
        hover_color="#a83232",
        command=lambda: delete_tag(app, tag)
    ).grid(row=0, column=8, padx=4)


def set_tag_flag(app, tag, field, value):
    setattr(tag, field, value)

    if field == "enabled_sim":
        app.generate_signals()
    elif field == "enabled_trend" and hasattr(app, "trend_selector_frame"):
        from ui.trend_tab import create_ai_checkboxes

        create_ai_checkboxes(app)
    elif field == "enabled_alarm" and hasattr(app, "alarm_source_menu"):
        from ui.alarm_tab import update_alarm_sources

        update_alarm_sources(app)
    elif field == "enabled_dashboard" and hasattr(app, "dashboard_tags_frame"):
        from ui.dashboard_tab import update_dashboard

        update_dashboard(app, "Dashboard atualizado")

    if field != "enabled_sim" and hasattr(app, "update_pid_sources"):
        app.update_pid_sources()


def delete_tag(app, tag):
    if tag in app.tags:
        app.tags.remove(tag)

    refresh_tag_table(app)
    app.generate_signals()


def get_input_bool_tags(app):
    return [
        tag for tag in app.tags
        if tag.direction == "Input"
        and tag.data_type == "BOOL"
        and tag.enabled_sim
    ]


def get_input_analog_tags(app):
    return [
        tag for tag in app.tags
        if tag.direction == "Input"
        and tag.data_type in ["INT", "REAL"]
        and tag.enabled_sim
    ]


def get_trend_tags(app):
    return [
        tag for tag in app.tags
        if tag.enabled_trend
    ]


def get_alarm_tags(app):
    return [
        tag for tag in app.tags
        if tag.enabled_alarm
    ]


def get_dashboard_tags(app):
    return [
        tag for tag in getattr(app, "tags", [])
        if tag.enabled_dashboard
    ]


def get_numeric_tags(app):
    return [
        tag for tag in getattr(app, "tags", [])
        if tag.data_type in ["INT", "REAL"]
    ]


def get_pid_output_tags(app):
    return [
        tag for tag in get_numeric_tags(app)
        if tag.direction in ["Input", "Internal", "Output"]
    ]


def get_tag_by_name(app, name):
    return next(
        (tag for tag in getattr(app, "tags", []) if tag.name == name),
        None,
    )


def get_feedback_tags(app):
    return [
        tag for tag in app.tags
        if tag.direction == "Feedback"
    ]
