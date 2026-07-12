"""Scalable master-detail Trends user interface."""

import csv
import logging
import math
import time
from tkinter import Menu, TclError, filedialog, messagebox, ttk

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ui.scrollable_frame import widget_exists
from ui.table_utils import clear_entry, copy_text, debounce, filter_tags, move_selection, page_tags, sort_tags


LOGGER = logging.getLogger(__name__)
COLORS = ["blue", "green", "orange", "purple", "cyan", "brown", "magenta", "olive"]
TREND_FILTERS = ("All", "Enabled", "Disabled", "BOOL", "INT", "REAL", "Visible", "Hidden")


def default_trend_config(index=0):
    return {
        "color": COLORS[index % len(COLORS)], "line_width": 2.0, "axis": "Left",
        "visible": True, "sample_rate_ms": 1000, "history_size": 120,
        "buffer_size": 120,
    }


def create_trend_tab(app):
    """Create the fixed Trends structure exactly once."""
    if getattr(app, "_trend_structure_initialized", False):
        return
    started = time.perf_counter()
    app.trend_running = False
    app.trend_start_time = time.time()
    app.trend_data = {"time": [], "tags": {}}
    app.trend_auto_scale = ctk.BooleanVar(value=True)
    app.trend_visible_tags = {
        tag.name for tag in getattr(app, "tags", []) if tag.enabled_trend
    }
    app.trend_tag_vars = {}  # compatibility: deliberately contains no per-tag Tk variables
    app._trend_configs = {}
    app._trend_table_tags = []
    app._trend_selected_tag_name = None
    app._trend_sort_column = "name"
    app._trend_sort_descending = False
    app.trend_page = 0
    app._trend_after_jobs = set()
    app._trend_structure_initialized = True

    frame = app.trend_frame = ctk.CTkFrame(app.tab_trends)
    frame.pack(fill="both", expand=True, padx=10, pady=10)
    controls = ctk.CTkFrame(frame)
    controls.pack(fill="x", padx=8, pady=(8, 4))
    app.trend_status = ctk.CTkLabel(controls, text="Trend OFF", text_color="gray", font=("Arial", 15, "bold"))
    app.trend_status.pack(side="left", padx=8)
    for text, command, width in (("Start Trend", start_trend, 110), ("Stop Trend", stop_trend, 110), ("Clear", clear_trend, 75), ("Export CSV", export_csv, 105)):
        ctk.CTkButton(controls, text=text, width=width, command=lambda fn=command: fn(app)).pack(side="left", padx=4)
    ctk.CTkCheckBox(controls, text="Auto Scale", variable=app.trend_auto_scale, command=lambda: redraw_trend(app)).pack(side="left", padx=10)

    body = ctk.CTkFrame(frame)
    body.pack(fill="both", expand=True, padx=8, pady=4)
    left = ctk.CTkFrame(body, width=380)
    left.pack(side="left", fill="y", expand=False, padx=(0, 6))
    left.pack_propagate(False)
    right = ctk.CTkFrame(body)
    right.pack(side="right", fill="both", expand=True, padx=(6, 0))
    search = ctk.CTkFrame(left)
    search.pack(fill="x", padx=6, pady=6)
    ctk.CTkLabel(search, text="Search").pack(side="left", padx=(3, 2))
    app.trend_search_entry = ctk.CTkEntry(search, width=250, placeholder_text="Name, address or type")
    app.trend_search_entry.pack(side="left", padx=3)
    ctk.CTkButton(search, text="×", width=30, command=lambda: clear_trend_search(app)).pack(side="left", padx=(0, 6))
    filters = ctk.CTkFrame(left)
    filters.pack(fill="x", padx=6, pady=(0, 6))
    ctk.CTkLabel(filters, text="Filter").pack(side="left", padx=(3, 8))
    app.trend_filter_menu = ctk.CTkOptionMenu(filters, values=list(TREND_FILTERS), width=150, command=lambda _v: refresh_trend_selectors(app, reset_page=True))
    app.trend_filter_menu.set("All")
    app.trend_filter_menu.pack(side="left", padx=3)
    app.trend_search_entry.bind("<KeyRelease>", lambda event: _trend_search_key(app, event))
    app.trend_search_entry.bind("<Escape>", lambda _e: clear_trend_search(app))
    app.tab_trends.bind("<Control-f>", lambda _e: app.trend_search_entry.focus_set())

    table_frame = ctk.CTkFrame(left)
    table_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))
    columns = ("status", "name", "address", "type", "value")
    app.trend_table = ttk.Treeview(table_frame, columns=columns, show="headings", height=16)
    for column, title, width in (("status", "Status", 58), ("name", "Name", 115), ("address", "Address", 75), ("type", "Type", 45), ("value", "Value", 65)):
        app.trend_table.heading(column, text=title, command=lambda col=column: sort_trend_table(app, col))
        app.trend_table.column(column, width=width, anchor="w" if column == "name" else "center")
    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=app.trend_table.yview)
    app.trend_table.configure(yscrollcommand=scrollbar.set)
    app.trend_table.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    app.trend_table.bind("<<TreeviewSelect>>", lambda _e: bind_selected_trend(app))
    app.trend_table.bind("<Double-1>", lambda _e: toggle_selected_trend(app))
    app.trend_table.bind("<Button-3>", lambda e: show_trend_context_menu(app, e))
    app.trend_table.bind("<Key>", lambda e: handle_trend_key(app, e))
    paging = ctk.CTkFrame(left)
    paging.pack(fill="x", padx=6, pady=(0, 5))
    app.trend_count_label = ctk.CTkLabel(paging, text="No tags")
    app.trend_count_label.pack(side="left", padx=4)
    app.trend_page_size_menu = ctk.CTkOptionMenu(paging, values=["25", "50", "100", "250"], width=70, command=lambda _v: refresh_trend_selectors(app, reset_page=True))
    app.trend_page_size_menu.set("50"); app.trend_page_size_menu.pack(side="right", padx=3)
    app.trend_next_button = ctk.CTkButton(paging, text="Next", width=55, command=lambda: change_trend_page(app, 1)); app.trend_next_button.pack(side="right", padx=3)
    app.trend_previous_button = ctk.CTkButton(paging, text="Previous", width=65, command=lambda: change_trend_page(app, -1)); app.trend_previous_button.pack(side="right", padx=3)

    editor = app.trend_editor = ctk.CTkFrame(right)
    editor.pack(side="bottom", fill="x", padx=6, pady=(6, 6))
    app.trend_editor_title = ctk.CTkLabel(editor, text="Select a trend tag", font=("Arial", 14, "bold"))
    app.trend_editor_title.grid(row=0, column=0, columnspan=8, sticky="w", padx=12, pady=(10, 5))
    app.trend_editor_fields = {}
    specs = (
        ("enabled", "Trend enabled", "switch", None), ("color", "Color", "menu", COLORS),
        ("line_width", "Line width", "entry", None), ("axis", "Axis", "menu", ["Left", "Right"]),
        ("visible", "Visible", "switch", None), ("sample_rate_ms", "Sample rate (ms)", "entry", None),
        ("history_size", "History size", "entry", None), ("buffer_size", "Buffer size", "entry", None),
    )
    for index, (key, label, kind, values) in enumerate(specs):
        group, band = index % 4, index // 4
        label_row, widget_row, column = 1 + band * 2, 2 + band * 2, group * 2
        editor.grid_columnconfigure(column + 1, weight=1)
        ctk.CTkLabel(editor, text=label, anchor="w").grid(row=label_row, column=column, columnspan=2, sticky="w", padx=(10, 4), pady=(3, 0))
        if kind == "switch": widget = ctk.CTkSwitch(editor, text="", width=55)
        elif kind == "menu": widget = ctk.CTkOptionMenu(editor, values=values, width=125)
        else: widget = ctk.CTkEntry(editor, width=125)
        widget.grid(row=widget_row, column=column, columnspan=2, sticky="ew", padx=(10, 8), pady=(1, 4))
        app.trend_editor_fields[key] = widget
    buttons = ctk.CTkFrame(editor)
    buttons.grid(row=5, column=0, columnspan=8, sticky="ew", padx=8, pady=(5, 9))
    for index, (text, action) in enumerate((("Enable Trend", True), ("Disable Trend", False), ("Show", "show"), ("Hide", "hide"), ("Remove from Trend", "remove"))):
        ctk.CTkButton(buttons, text=text, width=125, command=lambda value=action: trend_editor_action(app, value)).grid(row=index // 2, column=index % 2, padx=3, pady=3)
    for widget in app.trend_editor_fields.values():
        widget.configure(state="disabled")
    app.trend_editor_fields["enabled"].configure(command=lambda: apply_trend_editor(app))
    app.trend_editor_fields["visible"].configure(command=lambda: apply_trend_editor(app))
    app.trend_editor_fields["color"].configure(command=lambda _v: apply_trend_editor(app))
    app.trend_editor_fields["axis"].configure(command=lambda _v: apply_trend_editor(app))
    for key in ("line_width", "sample_rate_ms", "history_size", "buffer_size"):
        app.trend_editor_fields[key].bind("<FocusOut>", lambda _e: apply_trend_editor(app))
        app.trend_editor_fields[key].bind("<Return>", lambda _e: apply_trend_editor(app))

    app.trend_fig = Figure(figsize=(8, 4), dpi=100)
    app.trend_ax = app.trend_fig.add_subplot(111)
    app.trend_fig.set_facecolor("white")
    app.trend_ax.set_facecolor("white")
    configure_axes(app)
    app.trend_canvas = FigureCanvasTkAgg(app.trend_fig, master=right)
    app.trend_canvas.draw()
    app.trend_canvas.get_tk_widget().pack(side="top", fill="both", expand=True, padx=6, pady=(6, 0))
    refresh_trend_selectors(app)
    LOGGER.info("Trends master-detail created: widgets_created=38 per_tag_widgets=0 structure_time_ms=%.3f", (time.perf_counter() - started) * 1000)


def _trend_search_key(app, event):
    if getattr(event, "keysym", "") == "Escape": clear_trend_search(app); return
    debounce(app, "trend_search", 150, lambda: refresh_trend_selectors(app, reset_page=True))


def clear_trend_search(app):
    clear_entry(app.trend_search_entry)
    refresh_trend_selectors(app, reset_page=True)


def _trend_config(app, tag):
    configs = getattr(app, "_trend_configs", {})
    if tag.name not in configs:
        configs[tag.name] = default_trend_config(len(configs))
        if hasattr(app, "trend_visible_tags"):
            configs[tag.name]["visible"] = tag.name in app.trend_visible_tags
    app._trend_configs = configs
    return configs[tag.name]


def _filtered_trend_tags(app):
    tags = filter_tags(getattr(app, "tags", []), app.trend_search_entry.get() if hasattr(app, "trend_search_entry") else "")
    selected_filter = app.trend_filter_menu.get() if hasattr(app, "trend_filter_menu") else "All"
    visible = getattr(app, "trend_visible_tags", set())
    if selected_filter == "Enabled": tags = [tag for tag in tags if tag.enabled_trend]
    elif selected_filter == "Disabled": tags = [tag for tag in tags if not tag.enabled_trend]
    elif selected_filter in ("BOOL", "INT", "REAL"): tags = [tag for tag in tags if tag.data_type == selected_filter]
    elif selected_filter == "Visible": tags = [tag for tag in tags if tag.name in visible]
    elif selected_filter == "Hidden": tags = [tag for tag in tags if tag.name not in visible]
    values = {tag.name: getattr(app, "tag_runtime", None).get_value(tag.name) if getattr(app, "tag_runtime", None) else None for tag in tags}
    return sort_tags(tags, app._trend_sort_column, app._trend_sort_descending, values=values)


def change_trend_page(app, offset):
    app.trend_page = max(0, getattr(app, "trend_page", 0) + offset)
    refresh_trend_selectors(app)


def refresh_trend_selectors(app, reset_page=False):
    """Refresh only lightweight Treeview rows; never rebuild Trends structure."""
    table = getattr(app, "trend_table", None)
    if table is None or not widget_exists(table): return
    started = time.perf_counter()
    selected = getattr(app, "_trend_selected_tag_name", None)
    tags = _filtered_trend_tags(app)
    if reset_page:
        app.trend_page = 0
        names = [tag.name for tag in tags]
        if selected in names:
            app.trend_page = names.index(selected) // int(app.trend_page_size_menu.get())
    page, page_count, start, visible_tags = page_tags(tags, app.trend_page, app.trend_page_size_menu.get())
    app.trend_page = page
    table.delete(*table.get_children())
    app._trend_table_tags = visible_tags
    selected_item = None
    for tag in visible_tags:
        item = table.insert("", "end", values=("● ON" if tag.enabled_trend else "○ OFF", tag.name, tag.address, tag.data_type, _display_value(app, tag)))
        if tag.name == selected: selected_item = item
    if selected_item is None and table.get_children(): selected_item = table.get_children()[0]
    if selected_item is not None:
        table.selection_set(selected_item); table.focus(selected_item); bind_selected_trend(app)
    else:
        app._trend_selected_tag_name = None; _set_editor_enabled(app, False)
        app.trend_editor_title.configure(text="No matching trend tags")
    app.trend_count_label.configure(text=f"Page {page + 1}/{page_count} · {len(tags)} of {len(getattr(app, 'tags', []))}")
    app.trend_previous_button.configure(state="normal" if page else "disabled")
    app.trend_next_button.configure(state="normal" if page + 1 < page_count else "disabled")
    titles = {"status":"Status", "name":"Name", "address":"Address", "type":"Type", "value":"Current value"}
    for column, title in titles.items():
        marker = (" ▼" if app._trend_sort_descending else " ▲") if column == app._trend_sort_column else ""
        table.heading(column, text=title + marker, command=lambda col=column: sort_trend_table(app, col))
    LOGGER.debug("Trend table refreshed: visible=%d matching=%d total=%d time_ms=%.3f", len(visible_tags), len(tags), len(getattr(app, "tags", [])), (time.perf_counter() - started) * 1000)


def update_trend_table_values(app):
    table = getattr(app, "trend_table", None)
    if table is None or not widget_exists(table): return
    for item, tag in zip(table.get_children(), app._trend_table_tags):
        values = list(table.item(item, "values")); values[0] = "● ON" if tag.enabled_trend else "○ OFF"; values[4] = _display_value(app, tag)
        table.item(item, values=values)


def _display_value(app, tag):
    value = app.tag_runtime.get_value(tag.name) if getattr(app, "tag_runtime", None) else None
    return "—" if value is None else str(value)


def sort_trend_table(app, column):
    if app._trend_sort_column == column: app._trend_sort_descending = not app._trend_sort_descending
    else: app._trend_sort_column, app._trend_sort_descending = column, False
    refresh_trend_selectors(app, reset_page=True)


def selected_trend_tag(app):
    selection = app.trend_table.selection()
    if not selection: return None
    index = app.trend_table.index(selection[0])
    return app._trend_table_tags[index] if index < len(app._trend_table_tags) else None


def _set_editor_enabled(app, enabled):
    if getattr(app, "_trend_editor_active", None) is bool(enabled):
        return
    for widget in app.trend_editor_fields.values(): widget.configure(state="normal" if enabled else "disabled")
    app._trend_editor_active = bool(enabled)


def bind_selected_trend(app):
    tag = selected_trend_tag(app)
    if tag is None: return
    app._trend_selected_tag_name = tag.name
    config = _trend_config(app, tag)
    _set_editor_enabled(app, True)
    app.trend_editor_title.configure(text=f"{tag.name} · {tag.address} · {tag.data_type}")
    fields = app.trend_editor_fields
    fields["enabled"].select() if tag.enabled_trend else fields["enabled"].deselect()
    fields["visible"].select() if config["visible"] else fields["visible"].deselect()
    fields["color"].set(config["color"]); fields["axis"].set(config["axis"])
    for key in ("line_width", "sample_rate_ms", "history_size", "buffer_size"):
        fields[key].delete(0, "end"); fields[key].insert(0, str(config[key]))


def apply_trend_editor(app):
    tag = selected_trend_tag(app)
    if tag is None: return
    fields, config = app.trend_editor_fields, _trend_config(app, tag)
    before = (tag.enabled_trend, tuple(config.items()))
    tag.enabled_trend = bool(fields["enabled"].get())
    config["visible"] = bool(fields["visible"].get())
    config["color"], config["axis"] = fields["color"].get(), fields["axis"].get()
    for key, cast, minimum in (("line_width", float, 0.1), ("sample_rate_ms", int, 50), ("history_size", int, 1), ("buffer_size", int, 1)):
        try: config[key] = max(minimum, cast(fields[key].get()))
        except (TypeError, ValueError): pass
    if config["visible"]: app.trend_visible_tags.add(tag.name)
    else: app.trend_visible_tags.discard(tag.name)
    if before != (tag.enabled_trend, tuple(config.items())) and hasattr(app, "mark_project_dirty"): app.mark_project_dirty()
    update_trend_table_values(app); redraw_trend(app)


def trend_editor_action(app, action):
    tag = selected_trend_tag(app)
    if tag is None: return
    if action in (True, False): app.trend_editor_fields["enabled"].select() if action else app.trend_editor_fields["enabled"].deselect()
    elif action in ("show", "hide"): app.trend_editor_fields["visible"].select() if action == "show" else app.trend_editor_fields["visible"].deselect()
    elif action == "remove":
        app.trend_editor_fields["enabled"].deselect(); app.trend_editor_fields["visible"].deselect(); app.trend_data.get("tags", {}).pop(tag.name, None)
    apply_trend_editor(app)


def toggle_selected_trend(app):
    tag = selected_trend_tag(app)
    if tag is not None: trend_editor_action(app, not tag.enabled_trend)


def handle_trend_key(app, event):
    key = event.keysym
    if key in ("Up", "Down", "Prior", "Next", "Home", "End"): move_selection(app.trend_table, key); bind_selected_trend(app); return "break"
    if key in ("space", "Return"): toggle_selected_trend(app); return "break"
    if key == "Delete": trend_editor_action(app, "remove"); return "break"


def show_trend_context_menu(app, event):
    row = app.trend_table.identify_row(event.y)
    if row: app.trend_table.selection_set(row); bind_selected_trend(app)
    tag = selected_trend_tag(app)
    if tag is None: return
    menu = Menu(app.trend_table, tearoff=False)
    menu.add_command(label="Enable Trend", command=lambda: trend_editor_action(app, True)); menu.add_command(label="Disable Trend", command=lambda: trend_editor_action(app, False))
    menu.add_command(label="Show", command=lambda: trend_editor_action(app, "show")); menu.add_command(label="Hide", command=lambda: trend_editor_action(app, "hide")); menu.add_separator()
    menu.add_command(label="Copy Name", command=lambda: copy_text(app.trend_table, tag.name)); menu.add_command(label="Copy Address", command=lambda: copy_text(app.trend_table, tag.address))
    menu.tk_popup(event.x_root, event.y_root)


def cancel_trend_callbacks(app):
    job = getattr(app, "_trend_search_debounce_job", None)
    if job is not None:
        try: app.cancel_job(job)
        except (TclError, ValueError): pass
        app._trend_search_debounce_job = None
    for job in tuple(getattr(app, "_trend_after_jobs", set())):
        try: app.cancel_job(job)
        except (TclError, ValueError): pass
    getattr(app, "_trend_after_jobs", set()).clear()
    canvas = getattr(app, "trend_canvas", None)
    idle_job = getattr(canvas, "_idle_draw_id", None)
    if idle_job is not None:
        try: canvas.get_tk_widget().after_cancel(idle_job)
        except (TclError, ValueError): pass
        canvas._idle_draw_id = None


def configure_axes(app):
    app.trend_ax.set_title("Trend de Tags"); app.trend_ax.set_xlabel("Tempo [s]"); app.trend_ax.set_ylabel("Valor"); app.trend_ax.grid(True, color="#cccccc", linestyle="-", linewidth=0.7)


def start_trend(app):
    if app.trend_running: return
    app.trend_running = True; app.trend_status.configure(text="Trend ON", text_color="lime"); update_trend(app)


def stop_trend(app):
    app.trend_running = False
    if hasattr(app, "trend_status") and widget_exists(app.trend_status): app.trend_status.configure(text="Trend OFF", text_color="gray")


def clear_trend(app):
    app.trend_data = {"time": [], "tags": {}}; app.trend_start_time = time.time(); redraw_trend(app)


def update_trend(app):
    if getattr(app, "is_closing", False) or getattr(app, "_shutdown_started", False) or not app.trend_running: return
    elapsed = round(time.time() - app.trend_start_time, 1); app.trend_data["time"].append(elapsed)
    enabled_tags = [tag for tag in getattr(app, "tags", []) if tag.enabled_trend]; enabled_names = {tag.name for tag in enabled_tags}
    for name in list(app.trend_data["tags"]):
        if name not in enabled_names: del app.trend_data["tags"][name]
    sample_count = len(app.trend_data["time"])
    for tag in enabled_tags:
        app.trend_data["tags"].setdefault(tag.name, [None] * (sample_count - 1)).append(_numeric_value(app.tag_runtime.get_value(tag.name)))
    max_points = max((_trend_config(app, tag)["buffer_size"] for tag in enabled_tags), default=120)
    if len(app.trend_data["time"]) > max_points:
        app.trend_data["time"] = app.trend_data["time"][-max_points:]
        for name in app.trend_data["tags"]: app.trend_data["tags"][name] = app.trend_data["tags"][name][-max_points:]
    redraw_trend(app); update_trend_table_values(app)
    job = None
    def scheduled():
        app._trend_after_jobs.discard(job); update_trend(app)
    job = app.schedule_job(1000, scheduled)
    if job is not None: app._trend_after_jobs.add(job)


def _numeric_value(value):
    if isinstance(value, bool): return int(value)
    try: numeric = value if isinstance(value, (int, float)) else float(value)
    except (TypeError, ValueError): return None
    return numeric if math.isfinite(numeric) else None


def _csv_value(value):
    return "" if value is None or isinstance(value, float) and not math.isfinite(value) else value


def redraw_trend(app):
    if not hasattr(app, "trend_ax"): return
    app.trend_ax.clear(); configure_axes(app); times = app.trend_data["time"]
    enabled_names = {tag.name for tag in getattr(app, "tags", []) if tag.enabled_trend}
    for index, (name, values) in enumerate(app.trend_data["tags"].items()):
        if name not in enabled_names: continue
        config = app._trend_configs.get(name, default_trend_config(index))
        if not config.get("visible", True): continue
        if len(values) == len(times): app.trend_ax.plot(times, values, label=name, linewidth=config.get("line_width", 2), color=config.get("color", COLORS[index % len(COLORS)]))
    if app.trend_auto_scale.get(): app.trend_ax.relim(); app.trend_ax.autoscale_view()
    else: app.trend_ax.set_ylim(0, 27648)
    if app.trend_ax.lines: app.trend_ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", borderaxespad=0)
    app.trend_fig.tight_layout(); app.trend_canvas.draw_idle()


def export_csv(app):
    file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile="trend_export.csv")
    if not file_path: return
    enabled_names = {tag.name for tag in getattr(app, "tags", []) if tag.enabled_trend}; tag_names = [name for name in app.trend_data["tags"] if name in enabled_names]
    try:
        with open(file_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file); writer.writerow(["time_s"] + tag_names)
            for index, elapsed in enumerate(app.trend_data["time"]): writer.writerow([elapsed] + [_csv_value(app.trend_data["tags"].get(name, [])[index] if index < len(app.trend_data["tags"].get(name, [])) else "") for name in tag_names])
    except OSError:
        LOGGER.exception("Trend CSV export failed: %s", file_path); messagebox.showerror("Erro Export CSV", "Unable to export CSV. Check file path and permissions."); return
    app.status_label.configure(text="● TREND EXPORTADA", text_color="lime"); LOGGER.info("Trend CSV exported: %s", file_path)
