import customtkinter as ctk

from ui.scrollable_frame import SafeScrollableFrame
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

    app.feedback_table = SafeScrollableFrame(frame)
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
    for row in app.feedback_rows:
        tag = row["tag"]
        value = app.tag_runtime.get_value(tag.name)

        if value is None:
            row["led"].configure(
                text="●" if tag.data_type == "BOOL" else "",
                text_color="gray"
            )
            row["value"].configure(text="---")
            continue

        if tag.data_type == "BOOL":
            row["led"].configure(text="●", text_color="lime" if value else "gray")
            row["value"].configure(text="1" if value else "0")
        else:
            row["led"].configure(text="")
            row["value"].configure(text=str(value))
