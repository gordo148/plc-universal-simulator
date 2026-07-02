import customtkinter as ctk

SCHNEIDER_MODELS = {
    "M221": {"coil_start": 0, "reg_start": 0, "description": "M221 / Machine Expert Basic"},
    "M241": {"coil_start": 0, "reg_start": 0, "description": "M241 / Machine Expert"},
    "M340": {"coil_start": 1000, "reg_start": 1000, "description": "M340 / Control Expert"},
    "M580": {"coil_start": 1000, "reg_start": 1000, "description": "M580 / Control Expert"},
}


def create_header(app):
    app.header = ctk.CTkFrame(app.app)
    app.header.pack(fill="x", padx=10, pady=10)

    ctk.CTkLabel(app.header, text="Marca").grid(row=0, column=0, padx=5)
    app.brand_menu = ctk.CTkOptionMenu(
        app.header,
        values=["Siemens", "Schneider"],
        command=app.update_brand
    )
    app.brand_menu.set("Siemens")
    app.brand_menu.grid(row=0, column=1, padx=5)

    ctk.CTkLabel(app.header, text="IP").grid(row=0, column=2, padx=5)
    app.ip_entry = ctk.CTkEntry(app.header, width=140)
    app.ip_entry.insert(0, "192.168.1.10")
    app.ip_entry.grid(row=0, column=3, padx=5)

    ctk.CTkButton(app.header, text="Ligar", command=app.connect, width=80).grid(row=0, column=4, padx=4)
    ctk.CTkButton(app.header, text="Desligar", command=app.disconnect, width=80).grid(row=0, column=5, padx=4)
    ctk.CTkButton(app.header, text="Gerar", command=app.generate_signals, width=80).grid(row=0, column=6, padx=4)
    ctk.CTkButton(app.header, text="Reset", command=app.reset_all, width=80).grid(row=0, column=7, padx=4)
    ctk.CTkButton(app.header, text="Guardar", command=app.save_project, width=80).grid(row=0, column=8, padx=4)
    ctk.CTkButton(app.header, text="Carregar", command=app.load_project, width=80).grid(row=0, column=9, padx=4)

    app.status_label = ctk.CTkLabel(
        app.header,
        text="● DESLIGADO",
        text_color="red",
        font=("Arial", 14, "bold")
    )
    app.status_label.grid(row=0, column=10, padx=15)

    app.brand_frame = ctk.CTkFrame(app.header)
    app.brand_frame.grid(row=1, column=0, columnspan=11, sticky="ew", padx=5, pady=10)

    app.create_siemens_options = lambda: create_siemens_options(app)
    app.create_schneider_options = lambda: create_schneider_options(app)
    app.create_siemens_options()


def clear_brand_frame(app):
    for widget in app.brand_frame.winfo_children():
        widget.destroy()


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
