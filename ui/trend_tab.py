import time
import csv
import customtkinter as ctk
from tkinter import filedialog
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


COLORS = [
    "blue",
    "green",
    "orange",
    "purple",
    "cyan",
    "brown",
    "magenta",
    "olive",
]


def create_trend_tab(app):
    app.trend_running = False
    app.trend_start_time = time.time()

    app.trend_data = {
        "time": [],
        "ai": {},
        "pid_pv": [],
        "pid_out": []
    }

    app.trend_ai_vars = {}
    app.trend_show_pid_pv = ctk.BooleanVar(value=True)
    app.trend_show_pid_out = ctk.BooleanVar(value=True)
    app.trend_auto_scale = ctk.BooleanVar(value=True)

    frame = ctk.CTkFrame(app.tab_trends)
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    controls = ctk.CTkFrame(frame)
    controls.pack(fill="x", padx=10, pady=10)

    app.trend_status = ctk.CTkLabel(
        controls,
        text="Trend OFF",
        text_color="gray",
        font=("Arial", 16, "bold")
    )
    app.trend_status.pack(side="left", padx=10)

    ctk.CTkButton(controls, text="Start Trend", command=lambda: start_trend(app), width=120).pack(side="left", padx=8)
    ctk.CTkButton(controls, text="Stop Trend", command=lambda: stop_trend(app), width=120).pack(side="left", padx=8)
    ctk.CTkButton(controls, text="Limpar", command=lambda: clear_trend(app), width=100).pack(side="left", padx=8)
    ctk.CTkButton(controls, text="Exportar CSV", command=lambda: export_csv(app), width=130).pack(side="left", padx=8)

    ctk.CTkCheckBox(
        controls,
        text="Auto Scale",
        variable=app.trend_auto_scale,
        command=lambda: redraw_trend(app)
    ).pack(side="left", padx=12)

    selector = ctk.CTkFrame(frame)
    selector.pack(fill="x", padx=10, pady=5)

    app.trend_selector_frame = selector

    ctk.CTkCheckBox(
        selector,
        text="PID PV",
        variable=app.trend_show_pid_pv,
        command=lambda: redraw_trend(app)
    ).pack(side="left", padx=8)

    ctk.CTkCheckBox(
        selector,
        text="PID OUT",
        variable=app.trend_show_pid_out,
        command=lambda: redraw_trend(app)
    ).pack(side="left", padx=8)

    create_ai_checkboxes(app)

    app.trend_fig = Figure(figsize=(10, 5), dpi=100)
    app.trend_ax = app.trend_fig.add_subplot(111)

    app.trend_fig.set_facecolor("white")
    app.trend_ax.set_facecolor("white")

    configure_axes(app)

    app.trend_canvas = FigureCanvasTkAgg(app.trend_fig, master=frame)
    app.trend_canvas.draw()
    app.trend_canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)


def create_ai_checkboxes(app):
    for widget in app.trend_selector_frame.winfo_children():
        text = widget.cget("text") if hasattr(widget, "cget") else ""
        if str(text).startswith("AI_"):
            widget.destroy()

    app.trend_ai_vars.clear()

    for i, item in enumerate(app.analog_widgets):
        name = item["name_entry"].get()
        var = ctk.BooleanVar(value=True)
        app.trend_ai_vars[name] = var

        ctk.CTkCheckBox(
            app.trend_selector_frame,
            text=name,
            variable=var,
            command=lambda: redraw_trend(app)
        ).pack(side="left", padx=8)


def configure_axes(app):
    app.trend_ax.set_title("Trend Analógicas / PID")
    app.trend_ax.set_xlabel("Tempo [s]")
    app.trend_ax.set_ylabel("Valor RAW")
    app.trend_ax.grid(True, color="#cccccc", linestyle="-", linewidth=0.7)


def start_trend(app):
    create_ai_checkboxes(app)

    app.trend_running = True
    app.trend_status.configure(text="Trend ON", text_color="lime")

    update_trend(app)


def stop_trend(app):
    app.trend_running = False
    app.trend_status.configure(text="Trend OFF", text_color="gray")


def clear_trend(app):
    app.trend_data = {
        "time": [],
        "ai": {},
        "pid_pv": [],
        "pid_out": []
    }

    app.trend_start_time = time.time()
    redraw_trend(app)


def update_trend(app):
    if not app.trend_running:
        return

    elapsed = round(time.time() - app.trend_start_time, 1)
    app.trend_data["time"].append(elapsed)

    for item in app.analog_widgets:
        name = item["name_entry"].get()

        try:
            value = int(item["live"].cget("text"))
        except Exception:
            value = 0

        if name not in app.trend_data["ai"]:
            app.trend_data["ai"][name] = []

        app.trend_data["ai"][name].append(value)

    try:
        pid_pv = int(app.pid_pv_label.cget("text").replace("PV:", "").strip())
    except Exception:
        pid_pv = 0

    try:
        pid_out = int(app.pid_out_label.cget("text").replace("OUT:", "").strip())
    except Exception:
        pid_out = 0

    app.trend_data["pid_pv"].append(pid_pv)
    app.trend_data["pid_out"].append(pid_out)

    max_points = 120

    if len(app.trend_data["time"]) > max_points:
        app.trend_data["time"] = app.trend_data["time"][-max_points:]

        for key in app.trend_data["ai"]:
            app.trend_data["ai"][key] = app.trend_data["ai"][key][-max_points:]

        app.trend_data["pid_pv"] = app.trend_data["pid_pv"][-max_points:]
        app.trend_data["pid_out"] = app.trend_data["pid_out"][-max_points:]

    redraw_trend(app)

    app.app.after(1000, lambda: update_trend(app))


def redraw_trend(app):
    app.trend_ax.clear()
    configure_axes(app)

    t = app.trend_data["time"]

    for idx, (name, values) in enumerate(app.trend_data["ai"].items()):
        show_curve = app.trend_ai_vars.get(name)

        if show_curve is not None and not show_curve.get():
            continue

        if len(values) == len(t):
            app.trend_ax.plot(
                t,
                values,
                label=name,
                linewidth=2,
                color=COLORS[idx % len(COLORS)]
            )

    if app.trend_show_pid_pv.get() and len(app.trend_data["pid_pv"]) == len(t):
        app.trend_ax.plot(
            t,
            app.trend_data["pid_pv"],
            label="PID PV",
            linewidth=2.5,
            color="black"
        )

    if app.trend_show_pid_out.get() and len(app.trend_data["pid_out"]) == len(t):
        app.trend_ax.plot(
            t,
            app.trend_data["pid_out"],
            label="PID OUT",
            linewidth=2.5,
            color="red"
        )

    if app.trend_auto_scale.get():
        app.trend_ax.relim()
        app.trend_ax.autoscale_view()
    else:
        app.trend_ax.set_ylim(0, 27648)

    if t:
        app.trend_ax.legend(
            bbox_to_anchor=(1.02, 1),
            loc="upper left",
            borderaxespad=0
        )

    app.trend_fig.tight_layout()
    app.trend_canvas.draw()


def export_csv(app):
    file_path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")],
        initialfile="trend_export.csv"
    )

    if not file_path:
        return

    ai_names = list(app.trend_data["ai"].keys())

    with open(file_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        header = ["time_s"] + ai_names + ["pid_pv", "pid_out"]
        writer.writerow(header)

        total = len(app.trend_data["time"])

        for i in range(total):
            row = [app.trend_data["time"][i]]

            for name in ai_names:
                values = app.trend_data["ai"].get(name, [])
                row.append(values[i] if i < len(values) else "")

            row.append(app.trend_data["pid_pv"][i] if i < len(app.trend_data["pid_pv"]) else "")
            row.append(app.trend_data["pid_out"][i] if i < len(app.trend_data["pid_out"]) else "")

            writer.writerow(row)

    app.status_label.configure(text="● TREND EXPORTADA", text_color="lime")