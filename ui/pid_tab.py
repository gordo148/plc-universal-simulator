import customtkinter as ctk


def create_pid_tab(app):
    frame = ctk.CTkFrame(app.tab_pid)
    frame.pack(padx=20, pady=20, fill="x")

    ctk.CTkLabel(frame, text="PID Externo", font=("Arial", 22, "bold")).grid(
        row=0, column=0, columnspan=6, pady=15
    )

    ctk.CTkLabel(frame, text="Setpoint").grid(row=1, column=0, padx=10, pady=8)
    app.pid_sp_entry = ctk.CTkEntry(frame, width=100)
    app.pid_sp_entry.insert(0, "10000")
    app.pid_sp_entry.grid(row=1, column=1, padx=10)

    ctk.CTkLabel(frame, text="PV Source").grid(row=1, column=2, padx=10)
    app.pid_pv_menu = ctk.CTkOptionMenu(frame, values=["AI_01"])
    app.pid_pv_menu.grid(row=1, column=3, padx=10)

    ctk.CTkLabel(frame, text="OUT Address").grid(row=1, column=4, padx=10)
    app.pid_out_entry = ctk.CTkEntry(frame, width=100)
    app.pid_out_entry.insert(0, "20")
    app.pid_out_entry.grid(row=1, column=5, padx=10)

    ctk.CTkLabel(frame, text="Kp").grid(row=2, column=0, padx=10, pady=8)
    app.pid_kp_entry = ctk.CTkEntry(frame, width=100)
    app.pid_kp_entry.insert(0, "1.0")
    app.pid_kp_entry.grid(row=2, column=1, padx=10)

    ctk.CTkLabel(frame, text="Ki").grid(row=2, column=2, padx=10)
    app.pid_ki_entry = ctk.CTkEntry(frame, width=100)
    app.pid_ki_entry.insert(0, "0.0")
    app.pid_ki_entry.grid(row=2, column=3, padx=10)

    ctk.CTkLabel(frame, text="Kd").grid(row=2, column=4, padx=10)
    app.pid_kd_entry = ctk.CTkEntry(frame, width=100)
    app.pid_kd_entry.insert(0, "0.0")
    app.pid_kd_entry.grid(row=2, column=5, padx=10)

    ctk.CTkLabel(frame, text="OUT Min").grid(row=3, column=0, padx=10, pady=8)
    app.pid_out_min_entry = ctk.CTkEntry(frame, width=100)
    app.pid_out_min_entry.insert(0, "0")
    app.pid_out_min_entry.grid(row=3, column=1, padx=10)

    ctk.CTkLabel(frame, text="OUT Max").grid(row=3, column=2, padx=10)
    app.pid_out_max_entry = ctk.CTkEntry(frame, width=100)
    app.pid_out_max_entry.insert(0, "27648")
    app.pid_out_max_entry.grid(row=3, column=3, padx=10)

    ctk.CTkLabel(frame, text="Intervalo ms").grid(row=3, column=4, padx=10)
    app.pid_interval_entry = ctk.CTkEntry(frame, width=100)
    app.pid_interval_entry.insert(0, "500")
    app.pid_interval_entry.grid(row=3, column=5, padx=10)

    app.pid_status_label = ctk.CTkLabel(frame, text="PID OFF", text_color="gray", font=("Arial", 16, "bold"))
    app.pid_status_label.grid(row=4, column=0, columnspan=2, pady=20)

    app.pid_pv_label = ctk.CTkLabel(frame, text="PV: 0", font=("Arial", 16))
    app.pid_pv_label.grid(row=4, column=2, pady=20)

    app.pid_out_label = ctk.CTkLabel(frame, text="OUT: 0", font=("Arial", 16))
    app.pid_out_label.grid(row=4, column=3, pady=20)

    ctk.CTkButton(frame, text="Start PID", command=app.start_pid, width=120).grid(row=4, column=4, padx=10)
    ctk.CTkButton(frame, text="Stop PID", command=app.stop_pid, width=120).grid(row=4, column=5, padx=10)

    ctk.CTkLabel(
        app.tab_pid,
        text="Siemens: OUT Address = byte DBW, exemplo 20. Schneider: OUT Address = %MW, exemplo 2000.",
        text_color="gray"
    ).pack(pady=10)