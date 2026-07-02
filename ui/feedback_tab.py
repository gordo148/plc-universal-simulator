import struct
import customtkinter as ctk
from snap7.util import get_bool, get_int, get_real
from ui.tag_manager import get_feedback_tags


def create_feedback_tab(app):
    app.feedback_rows = []

    frame = ctk.CTkFrame(app.tab_feedbacks)
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    controls = ctk.CTkFrame(frame)
    controls.pack(fill="x", padx=10, pady=10)

    app.feedback_status = ctk.CTkLabel(
        controls,
        text="Feedbacks",
        text_color="gray",
        font=("Arial", 16, "bold")
    )
    app.feedback_status.pack(side="left", padx=10)

    ctk.CTkButton(
        controls,
        text="Atualizar Feedbacks",
        command=lambda: refresh_feedback_table(app),
        width=160
    ).pack(side="left", padx=10)

    header = ctk.CTkFrame(frame)
    header.pack(fill="x", padx=10, pady=(10, 0))

    headers = ["Estado", "Nome", "Tipo", "Endereço", "Valor"]

    for col, text in enumerate(headers):
        ctk.CTkLabel(
            header,
            text=text,
            font=("Arial", 13, "bold"),
            width=160
        ).grid(row=0, column=col, padx=4, pady=6)

    app.feedback_table = ctk.CTkScrollableFrame(frame)
    app.feedback_table.pack(fill="both", expand=True, padx=10, pady=10)

    refresh_feedback_table(app)
    scan_feedbacks(app)


def refresh_feedback_table(app):
    if not hasattr(app, "feedback_table"):
        return

    for widget in app.feedback_table.winfo_children():
        widget.destroy()

    app.feedback_rows.clear()

    feedback_tags = get_feedback_tags(app)

    for tag in feedback_tags:
        create_feedback_row(app, tag)


def create_feedback_row(app, tag):
    row = ctk.CTkFrame(app.feedback_table)
    row.pack(fill="x", padx=5, pady=4)

    led = ctk.CTkLabel(
        row,
        text="●" if tag.data_type == "BOOL" else "",
        text_color="gray",
        font=("Arial", 24),
        width=160
    )
    led.grid(row=0, column=0, padx=4, pady=6)

    ctk.CTkLabel(row, text=tag.name, width=160).grid(row=0, column=1, padx=4)
    ctk.CTkLabel(row, text=tag.data_type, width=160).grid(row=0, column=2, padx=4)
    ctk.CTkLabel(row, text=tag.address, width=160).grid(row=0, column=3, padx=4)

    value = ctk.CTkLabel(row, text="---", width=160, font=("Arial", 15, "bold"))
    value.grid(row=0, column=4, padx=4)

    app.feedback_rows.append({
        "tag": tag,
        "led": led,
        "value": value
    })


def scan_feedbacks(app):
    if hasattr(app, "feedback_rows"):
        update_feedback_values(app)

    app.app.after(500, lambda: scan_feedbacks(app))


def update_feedback_values(app):
    if app.driver is None or not app.driver.is_connected():
        return

    for row in app.feedback_rows:
        tag = row["tag"]
        value = read_feedback_value(app, tag)

        if value is None:
            row["led"].configure(
                text="●" if tag.data_type == "BOOL" else "",
                text_color="gray"
            )
            row["value"].configure(text="---")
            continue

        tag.value = value

        if tag.data_type == "BOOL":
            row["led"].configure(text="●", text_color="lime" if value else "gray")
            row["value"].configure(text="1" if value else "0")
        else:
            row["led"].configure(text="")
            row["value"].configure(text=str(value))


def read_feedback_value(app, tag):
    try:
        if app.brand_menu.get() == "Siemens":
            return read_siemens_feedback(app, tag)

        return read_schneider_feedback(app, tag)

    except Exception:
        return None


def read_siemens_feedback(app, tag):
    data = app.driver.read_data(1000)

    if data is None:
        return None

    address = tag.address.strip().upper()

    if tag.data_type == "BOOL":
        address = address.replace("DBX", "")
        byte_text, bit_text = address.split(".")
        return get_bool(data, int(byte_text), int(bit_text))

    if tag.data_type == "INT":
        address = address.replace("DBW", "")
        return get_int(data, int(address))

    if tag.data_type == "REAL":
        address = address.replace("DBD", "")
        return round(get_real(data, int(address)), 3)

    return None


def read_schneider_feedback(app, tag):

    address = tag.address.strip().upper()

    if tag.data_type == "BOOL":
        address = address.replace("%M", "").replace("M", "")
        values = app.driver.read_coils_block(int(address), 1)

        if values is None:
            return None

        return bool(values[0])

    if tag.data_type == "INT":
        address = address.replace("%MW", "").replace("MW", "")
        values = app.driver.read_registers_block(int(address), 1)

        if values is None:
            return None

        return values[0]

    if tag.data_type == "REAL":
        address = address.replace("%MW", "").replace("MW", "")
        values = app.driver.read_registers_block(int(address), 2)

        if values is None or len(values) < 2:
            return None

        raw = struct.pack(">HH", values[0] & 0xFFFF, values[1] & 0xFFFF)
        return round(struct.unpack(">f", raw)[0], 3)

    return None
