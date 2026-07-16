import customtkinter as ctk
from ui.table_utils import tag_comment_tooltip


def update_pid_comment_labels(app):
    if not hasattr(app, "pid_comment_label"):
        return
    tags = {tag.name: tag for tag in getattr(app, "tags", [])}
    parts = []
    for label, menu_name in (("SP", "pid_sp_source_menu"), ("PV", "pid_pv_menu"), ("OUT", "pid_out_menu")):
        menu = getattr(app, menu_name, None)
        tag = tags.get(menu.get()) if menu is not None else None
        if tag is not None and tag.comment:
            parts.append(f"{label}: {tag.comment}")
    app.pid_comment_label.configure(text="Comments: " + (" · ".join(parts) if parts else "—"))


def create_pid_tab(app):
    frame = ctk.CTkFrame(app.tab_pid)
    frame.pack(padx=20, pady=20, fill="x")

    ctk.CTkLabel(frame, text="PID Externo", font=("Arial", 22, "bold")).grid(
        row=0, column=0, columnspan=6, pady=15
    )

    ctk.CTkLabel(frame, text="SP Source").grid(row=1, column=0, padx=10, pady=8)
    app.pid_sp_source_menu = ctk.CTkOptionMenu(frame, values=["Manual"], command=lambda _v: update_pid_comment_labels(app))
    app.pid_sp_source_menu.set("Manual")
    app.pid_sp_source_menu.grid(row=1, column=1, padx=10)

    ctk.CTkLabel(frame, text="SP Manual").grid(row=1, column=2, padx=10)
    app.pid_sp_entry = ctk.CTkEntry(frame, width=100)
    app.pid_sp_entry.insert(0, "10000")
    app.pid_sp_entry.grid(row=1, column=3, padx=10)

    ctk.CTkLabel(frame, text="PV Source").grid(row=1, column=4, padx=10)
    app.pid_pv_menu = ctk.CTkOptionMenu(frame, values=[], command=lambda _v: update_pid_comment_labels(app))
    app.pid_pv_menu.grid(row=1, column=5, padx=10)

    ctk.CTkLabel(frame, text="OUT Destination").grid(row=2, column=0, padx=10, pady=8)
    app.pid_out_menu = ctk.CTkOptionMenu(frame, values=[], command=lambda _v: update_pid_comment_labels(app))
    app.pid_out_menu.grid(row=2, column=1, padx=10)
    for menu in (app.pid_sp_source_menu, app.pid_pv_menu, app.pid_out_menu):
        tag_comment_tooltip(
            menu,
            lambda selected=menu: next(
                (tag for tag in getattr(app, "tags", []) if tag.name == selected.get()),
                None,
            ),
        )
    app.pid_comment_label = ctk.CTkLabel(frame, text="Comments: —", anchor="w", justify="left")
    app.pid_comment_label.grid(row=5, column=0, columnspan=6, sticky="ew", padx=10, pady=(2, 8))

    ctk.CTkLabel(frame, text="Kp").grid(row=2, column=2, padx=10)
    app.pid_kp_entry = ctk.CTkEntry(frame, width=100)
    app.pid_kp_entry.insert(0, "1.0")
    app.pid_kp_entry.grid(row=2, column=3, padx=10)

    ctk.CTkLabel(frame, text="Ki").grid(row=2, column=4, padx=10)
    app.pid_ki_entry = ctk.CTkEntry(frame, width=100)
    app.pid_ki_entry.insert(0, "0.0")
    app.pid_ki_entry.grid(row=2, column=5, padx=10)

    ctk.CTkLabel(frame, text="Kd").grid(row=3, column=0, padx=10, pady=8)
    app.pid_kd_entry = ctk.CTkEntry(frame, width=100)
    app.pid_kd_entry.insert(0, "0.0")
    app.pid_kd_entry.grid(row=3, column=1, padx=10)

    ctk.CTkLabel(frame, text="OUT Min").grid(row=3, column=2, padx=10)
    app.pid_out_min_entry = ctk.CTkEntry(frame, width=100)
    app.pid_out_min_entry.insert(0, "0")
    app.pid_out_min_entry.grid(row=3, column=3, padx=10)

    ctk.CTkLabel(frame, text="OUT Max").grid(row=3, column=4, padx=10)
    app.pid_out_max_entry = ctk.CTkEntry(frame, width=100)
    app.pid_out_max_entry.insert(0, "27648")
    app.pid_out_max_entry.grid(row=3, column=5, padx=10)

    ctk.CTkLabel(frame, text="Intervalo ms").grid(row=4, column=0, padx=10, pady=8)
    app.pid_interval_entry = ctk.CTkEntry(frame, width=100)
    app.pid_interval_entry.insert(0, "500")
    app.pid_interval_entry.grid(row=4, column=1, padx=10)

    app.pid_status_label = ctk.CTkLabel(
        frame,
        text="PID OFF",
        text_color="gray",
        font=("Arial", 16, "bold"),
    )
    app.pid_status_label.grid(row=4, column=2, pady=20)

    app.pid_pv_label = ctk.CTkLabel(frame, text="PV: 0", font=("Arial", 16))
    app.pid_pv_label.grid(row=4, column=3, pady=20)

    app.pid_out_label = ctk.CTkLabel(frame, text="OUT: 0", font=("Arial", 16))
    app.pid_out_label.grid(row=4, column=4, pady=20)

    controls = ctk.CTkFrame(app.tab_pid)
    controls.pack(pady=10)
    ctk.CTkButton(
        controls,
        text="Start PID",
        command=app.start_pid,
        width=120,
    ).pack(side="left", padx=10)
    ctk.CTkButton(
        controls,
        text="Stop PID",
        command=app.stop_pid,
        width=120,
    ).pack(side="left", padx=10)

    ctk.CTkLabel(
        app.tab_pid,
        text="SP and PV use numeric runtime tags. OUT uses an INT/REAL Input, Internal or Output tag.",
        text_color="gray",
    ).pack(pady=10)
