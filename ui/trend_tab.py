import csv
import logging
import math
import time
import customtkinter as ctk
from tkinter import filedialog, messagebox
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from ui.tag_manager import get_trend_tags


LOGGER = logging.getLogger(__name__)


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
    app.trend_data = {"time": [], "tags": {}}
    app.trend_tag_vars = {}
    app.trend_curve_widgets = []
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

    app.trend_selector_frame = ctk.CTkFrame(frame)
    app.trend_selector_frame.pack(fill="x", padx=10, pady=5)
    refresh_trend_selectors(app)

    app.trend_fig = Figure(figsize=(10, 5), dpi=100)
    app.trend_ax = app.trend_fig.add_subplot(111)
    app.trend_fig.set_facecolor("white")
    app.trend_ax.set_facecolor("white")
    configure_axes(app)

    app.trend_canvas = FigureCanvasTkAgg(app.trend_fig, master=frame)
    app.trend_canvas.draw()
    app.trend_canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)


def refresh_trend_selectors(app):
    """Refresh curve selectors from trend-enabled tags."""
    previous_selection = {
        name: variable.get()
        for name, variable in app.trend_tag_vars.items()
    }

    for widget in app.trend_curve_widgets:
        widget.destroy()

    app.trend_curve_widgets.clear()
    app.trend_tag_vars.clear()

    for tag in get_trend_tags(app):
        variable = ctk.BooleanVar(value=previous_selection.get(tag.name, True))
        app.trend_tag_vars[tag.name] = variable

        checkbox = ctk.CTkCheckBox(
            app.trend_selector_frame,
            text=tag.name,
            variable=variable,
            command=lambda: redraw_trend(app)
        )
        checkbox.pack(side="left", padx=8)
        app.trend_curve_widgets.append(checkbox)


def configure_axes(app):
    app.trend_ax.set_title("Trend de Tags")
    app.trend_ax.set_xlabel("Tempo [s]")
    app.trend_ax.set_ylabel("Valor")
    app.trend_ax.grid(True, color="#cccccc", linestyle="-", linewidth=0.7)


def start_trend(app):
    refresh_trend_selectors(app)

    if app.trend_running:
        return

    app.trend_running = True
    app.trend_status.configure(text="Trend ON", text_color="lime")
    update_trend(app)


def stop_trend(app):
    app.trend_running = False
    app.trend_status.configure(text="Trend OFF", text_color="gray")


def clear_trend(app):
    app.trend_data = {"time": [], "tags": {}}
    app.trend_start_time = time.time()
    redraw_trend(app)


def update_trend(app):
    if getattr(app, "is_closing", False):
        return
    if not app.trend_running:
        return

    elapsed = round(time.time() - app.trend_start_time, 1)
    app.trend_data["time"].append(elapsed)

    enabled_tags = get_trend_tags(app)
    enabled_names = {tag.name for tag in enabled_tags}

    for name in list(app.trend_data["tags"]):
        if name not in enabled_names:
            del app.trend_data["tags"][name]

    sample_count = len(app.trend_data["time"])
    for tag in enabled_tags:
        values = app.trend_data["tags"].setdefault(
            tag.name,
            [None] * (sample_count - 1)
        )
        values.append(_numeric_value(app.tag_runtime.get_value(tag.name)))

    max_points = 120
    if len(app.trend_data["time"]) > max_points:
        app.trend_data["time"] = app.trend_data["time"][-max_points:]
        for name in app.trend_data["tags"]:
            app.trend_data["tags"][name] = app.trend_data["tags"][name][-max_points:]

    redraw_trend(app)
    app.schedule_job(1000, lambda: update_trend(app))


def _numeric_value(value):
    if isinstance(value, bool):
        return int(value)

    if isinstance(value, (int, float)):
        numeric = value
    else:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None

    return numeric if math.isfinite(numeric) else None


def _csv_value(value):
    if value is None:
        return ""
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    return value


def redraw_trend(app):
    app.trend_ax.clear()
    configure_axes(app)

    times = app.trend_data["time"]
    enabled_names = {tag.name for tag in get_trend_tags(app)}

    for index, (name, values) in enumerate(app.trend_data["tags"].items()):
        if name not in enabled_names:
            continue

        show_curve = app.trend_tag_vars.get(name)
        if show_curve is not None and not show_curve.get():
            continue

        if len(values) == len(times):
            app.trend_ax.plot(
                times,
                values,
                label=name,
                linewidth=2,
                color=COLORS[index % len(COLORS)]
            )

    if app.trend_auto_scale.get():
        app.trend_ax.relim()
        app.trend_ax.autoscale_view()
    else:
        app.trend_ax.set_ylim(0, 27648)

    if app.trend_ax.lines:
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

    enabled_names = {tag.name for tag in get_trend_tags(app)}
    tag_names = [
        name for name in app.trend_data["tags"]
        if name in enabled_names
    ]

    try:
        with open(file_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["time_s"] + tag_names)

            for index, elapsed in enumerate(app.trend_data["time"]):
                row = [elapsed]
                for name in tag_names:
                    values = app.trend_data["tags"].get(name, [])
                    value = values[index] if index < len(values) else ""
                    row.append(_csv_value(value))
                writer.writerow(row)
    except OSError:
        LOGGER.exception("Trend CSV export failed: %s", file_path)
        messagebox.showerror(
            "Erro Export CSV",
            "Unable to export CSV. Check file path and permissions.",
        )
        return

    app.status_label.configure(text="● TREND EXPORTADA", text_color="lime")
    LOGGER.info("Trend CSV exported: %s", file_path)
