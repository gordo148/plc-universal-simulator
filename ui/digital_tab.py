import customtkinter as ctk


def create_digital_row(app, index, tag=None):
    row = ctk.CTkFrame(app.digital_scroll, corner_radius=15)
    row.pack(fill="x", padx=10, pady=6)

    app.digital_states[index] = False

    led = ctk.CTkLabel(row, text="●", text_color="gray", font=("Arial", 26))
    led.grid(row=0, column=0, padx=10, pady=8)

    if tag is not None:
        visible = tag.address
        protocol_address = tag.address
        address_data = parse_digital_address(app, tag.address)
        name = tag.name
    else:
        if app.brand_menu.get() == "Siemens":
            byte_index, bit_index, visible = app.get_siemens_digital_address(index)
            address_data = {"byte": byte_index, "bit": bit_index}
            protocol_address = visible
        else:
            address, visible = app.get_schneider_digital_address(index)
            address_data = {"coil": address}
            protocol_address = f"Coil {address}"

        name = f"DI_{index + 1:02d}"

    ctk.CTkLabel(row, text=visible, width=120, font=("Arial", 14, "bold")).grid(row=0, column=1, padx=10)
    ctk.CTkLabel(row, text=protocol_address, width=120, text_color="gray").grid(row=0, column=2, padx=10)

    name_entry = ctk.CTkEntry(row, width=230)
    name_entry.insert(0, name)
    name_entry.grid(row=0, column=3, padx=10)

    mode_menu = ctk.CTkOptionMenu(row, values=["Toggle", "Pulse"], width=100)
    mode_menu.set("Toggle")
    mode_menu.grid(row=0, column=4, padx=8)

    pulse_entry = ctk.CTkEntry(row, width=80)
    pulse_entry.insert(0, "500")
    pulse_entry.grid(row=0, column=5, padx=8)

    ctk.CTkLabel(row, text="ms", width=30).grid(row=0, column=6, padx=2)

    button = ctk.CTkButton(
        row,
        text=f"{name} OFF",
        width=160,
        command=lambda idx=index: app.digital_action(idx)
    )
    button.grid(row=0, column=7, padx=10)

    live = ctk.CTkLabel(row, text="0", width=40, font=("Arial", 16, "bold"))
    live.grid(row=0, column=8, padx=10)

    name_entry.bind("<KeyRelease>", lambda event, idx=index: app.update_digital_name(idx))

    app.digital_widgets.append({
        "led": led,
        "name_entry": name_entry,
        "button": button,
        "live": live,
        "address_data": address_data,
        "mode_menu": mode_menu,
        "pulse_entry": pulse_entry,
        "tag": tag
    })


def parse_digital_address(app, address):
    address = address.strip().upper()

    if app.brand_menu.get() == "Siemens":
        # Aceita DBX0.0 ou 0.0
        address = address.replace("DBX", "")
        byte_text, bit_text = address.split(".")

        return {
            "byte": int(byte_text),
            "bit": int(bit_text)
        }

    # Schneider: aceita %M1000 ou M1000 ou 1000
    address = address.replace("%M", "")
    address = address.replace("M", "")

    return {
        "coil": int(address)
    }