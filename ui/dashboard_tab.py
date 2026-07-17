"""Fixed-layout industrial overview with lightweight table models."""

from collections import deque
import os
import subprocess
import time
from tkinter import HORIZONTAL, Menu, PanedWindow, TclError, font, messagebox, ttk

import customtkinter as ctk

from core.version import APP_VERSION
from core.dashboard_model import (
    COLUMN_KEYS, COLUMN_REGISTRY, COLUMNS_BY_KEY, COMPACT_COLUMNS,
    calculate_auto_fit_width, dashboard_statistics,
    default_dashboard_preferences, filter_dashboard_population,
    move_visible_column, normalize_dashboard_preferences,
    ordered_visible_columns, set_column_visibility,
    sort_dashboard_population,
)
from ui.header import connection_brand, connection_value
from ui.table_utils import copy_text, debounce, filter_tags, move_selection, tag_comment_tooltip, treeview_tag_comment_tooltip
from ui.tag_manager import get_dashboard_tags


DASHBOARD_REFRESH_MS = 750
EVENT_LIMIT = 50
COLORS = {"green":"#22c55e", "red":"#ef4444", "amber":"#f59e0b", "neutral":"#94a3b8", "cyan":"#22d3ee"}
CARD_BG = "#182431"
BORDER = "#334155"
DASHBOARD_COLUMNS = COLUMN_KEYS
DASHBOARD_SORTABLE_COLUMNS = frozenset(
    column.key for column in COLUMN_REGISTRY if column.sortable
)


def dashboard_counts(app):
    tags = getattr(app, "tags", [])
    return {
        "total": len(tags),
        "simulation": sum(bool(tag.enabled_sim) for tag in tags),
        "trends": sum(bool(tag.enabled_trend) for tag in tags),
        "alarms": sum(bool(tag.enabled_alarm) for tag in tags),
        "dashboard": sum(bool(tag.enabled_dashboard) for tag in tags),
    }


def dashboard_alarm_summary(app):
    alarms = getattr(app, "alarms", [])
    active = [alarm for alarm in alarms if alarm.get("active", False)]
    unacked = [alarm for alarm in active if not alarm.get("ack", False)]
    high = [alarm for alarm in active if alarm.get("type") in ("HIGH HIGH", "LOW LOW")]
    latest = active[-1] if active else None
    cleared = next((event[2] for event in reversed(list(getattr(app,"dashboard_events",()))) if len(event) >= 3 and "alarm normal" in str(event[2]).casefold()), None)
    return {"active":len(active), "unacknowledged":len(unacked), "high_priority":len(high), "latest":latest, "latest_cleared":cleared}


def dashboard_summary_values(app):
    counts=dashboard_counts(app); connected=app.plc_service.is_connected(); brand=connection_brand(app); diagnostics=app.plc_service.diagnostics_snapshot()
    project=os.path.basename(getattr(app,"project_path","") or "No project"); endpoint="Internal Simulator" if brand=="Simulator" else connection_value(app,"ip")
    return {"PLC":("ONLINE" if connected else "OFFLINE", "green" if connected else "red"),"Brand":(brand,"neutral"),"Endpoint":(endpoint,"cyan"),"Project":(project,"neutral"),"Tags":(counts["total"],"neutral"),"Simulation":(counts["simulation"],"amber"),"Trends":(counts["trends"],"cyan"),"Alarms":(counts["alarms"],"amber"),"Dashboard":(counts["dashboard"],"cyan"),"Communication":("HEALTHY" if connected and not diagnostics["read_error_count"] else ("INACTIVE" if not connected else "DEGRADED"),"green" if connected and not diagnostics["read_error_count"] else ("neutral" if not connected else "amber")),"Last read":(_fmt_time(diagnostics["last_read_timestamp"]),"neutral"),"Read cycle":(f"{diagnostics['last_read_duration_ms']:.1f} ms","cyan")}


def filter_dashboard_tags(tags, query="", quick_filter="All", runtime=None):
    result = filter_tags(tags, query)
    if quick_filter in ("BOOL", "INT", "REAL"):
        result = [tag for tag in result if tag.data_type == quick_filter]
    elif quick_filter == "Simulated":
        result = [tag for tag in result if tag.enabled_sim]
    elif quick_filter == "PLC source":
        result = [tag for tag in result if runtime and runtime.get(tag.name) and getattr(runtime.get(tag.name).source,"value",None) == "PLC"]
    return result


def configure_dashboard_headings(tree, sort_callback, sort_column=None, descending=False):
    """Configure sortable headings without passing invalid optional commands."""
    for definition in COLUMN_REGISTRY:
        marker = (" ▼" if descending else " ▲") if definition.key == sort_column else ""
        heading_options = {"text": definition.label + marker}
        if definition.sortable:
            command = lambda col=definition.key: sort_callback(col)
            if callable(command):
                heading_options["command"] = command
        tree.heading(definition.key, **heading_options)


def dashboard_preferences(app):
    settings = getattr(app, "settings", None)
    ui_preferences = getattr(settings, "ui_preferences", {})
    preferences = normalize_dashboard_preferences(ui_preferences.get("dashboard_ui"))
    if settings is not None:
        settings.ui_preferences["dashboard_ui"] = preferences
    return preferences


def persist_dashboard_preferences(app, delay_ms=200):
    """Store in user settings; the application shutdown path flushes memory."""
    if not hasattr(app, "_save_settings"):
        return
    debounce(app, "dashboard_preferences", delay_ms, app._save_settings)


def apply_dashboard_column_layout(app):
    """Apply displaycolumns and widths without touching existing rows."""
    preferences = dashboard_preferences(app)
    table = app.dashboard_tag_table
    table.configure(displaycolumns=ordered_visible_columns(preferences))
    for key, width in preferences["full_layout"]["widths"].items():
        table.column(key, width=width)
    if hasattr(app, "dashboard_compact_button"):
        app.dashboard_compact_button.configure(
            text="Compact View: ON" if preferences["compact"] else "Compact View"
        )
    configure_dashboard_headings(
        table, lambda column: sort_dashboard(app, column),
        preferences["sort"]["column"], preferences["sort"]["descending"],
    )


def toggle_dashboard_column(app, column):
    preferences = dashboard_preferences(app)
    if preferences["compact"]:
        return
    visible = column not in preferences["full_layout"]["visible"]
    updated = set_column_visibility(preferences, column, visible)
    app.settings.ui_preferences["dashboard_ui"] = updated
    apply_dashboard_column_layout(app); persist_dashboard_preferences(app)


def reorder_dashboard_column(app, column, offset):
    preferences = dashboard_preferences(app)
    if preferences["compact"]:
        return
    app.settings.ui_preferences["dashboard_ui"] = move_visible_column(preferences, column, offset)
    apply_dashboard_column_layout(app); persist_dashboard_preferences(app)


def toggle_dashboard_compact_view(app):
    preferences = dashboard_preferences(app)
    if not preferences["compact"]:
        preferences["previous_full_layout"] = {
            "visible": list(preferences["full_layout"]["visible"]),
            "order": list(preferences["full_layout"]["order"]),
            "widths": dict(preferences["full_layout"]["widths"]),
        }
    preferences["compact"] = not preferences["compact"]
    app.settings.ui_preferences["dashboard_ui"] = preferences
    apply_dashboard_column_layout(app); persist_dashboard_preferences(app)


def restore_previous_dashboard_layout(app):
    preferences = dashboard_preferences(app)
    preferences["full_layout"] = normalize_dashboard_preferences({
        "full_layout": preferences["previous_full_layout"]
    })["full_layout"]
    preferences["compact"] = False
    app.settings.ui_preferences["dashboard_ui"] = preferences
    apply_dashboard_column_layout(app); persist_dashboard_preferences(app)


def restore_default_dashboard_layout(app):
    app.settings.ui_preferences["dashboard_ui"] = default_dashboard_preferences()
    app._dashboard_sort_column, app._dashboard_sort_descending = "name", False
    apply_dashboard_column_layout(app); persist_dashboard_preferences(app)
    refresh_dashboard_table(app)


def auto_fit_dashboard_column(app, column):
    if column not in COLUMNS_BY_KEY:
        return
    table = app.dashboard_tag_table; definition = COLUMNS_BY_KEY[column]
    tk_font = font.nametofont("TkDefaultFont", root=table)
    values = (table.set(item, column) for item in table.get_children())
    width = calculate_auto_fit_width(
        definition.label, values, tk_font.measure,
        definition.minimum_width, definition.maximum_width,
    )
    table.column(column, width=width)
    preferences = dashboard_preferences(app)
    preferences["full_layout"]["widths"][column] = width
    app.settings.ui_preferences["dashboard_ui"] = preferences
    persist_dashboard_preferences(app)


def auto_fit_visible_dashboard_columns(app):
    for column in ordered_visible_columns(dashboard_preferences(app)):
        auto_fit_dashboard_column(app, column)


def show_dashboard_columns_menu(app):
    preferences = dashboard_preferences(app)
    menu = Menu(app.dashboard_columns_button, tearoff=False)
    visible = set(preferences["full_layout"]["visible"])
    for definition in COLUMN_REGISTRY:
        label = ("☑ " if definition.key in visible else "☐ ") + definition.label
        state = "disabled" if definition.key == "name" or preferences["compact"] else "normal"
        menu.add_command(label=label, state=state, command=lambda key=definition.key: toggle_dashboard_column(app, key))
    menu.add_separator()
    move_menu = Menu(menu, tearoff=False)
    for definition in COLUMN_REGISTRY:
        column_menu = Menu(move_menu, tearoff=False)
        column_menu.add_command(label="Move Left", command=lambda key=definition.key: reorder_dashboard_column(app, key, -1))
        column_menu.add_command(label="Move Right", command=lambda key=definition.key: reorder_dashboard_column(app, key, 1))
        move_menu.add_cascade(label=definition.label, menu=column_menu, state="normal" if definition.key in visible and not preferences["compact"] else "disabled")
    menu.add_cascade(label="Reorder", menu=move_menu)
    fit_menu = Menu(menu, tearoff=False)
    for definition in COLUMN_REGISTRY:
        fit_menu.add_command(label=definition.label, command=lambda key=definition.key: auto_fit_dashboard_column(app, key))
    menu.add_cascade(label="Auto Fit", menu=fit_menu)
    menu.add_command(label="Auto Fit Visible Columns", command=lambda: auto_fit_visible_dashboard_columns(app))
    menu.add_separator()
    menu.add_command(label="Compact View", command=lambda: toggle_dashboard_compact_view(app))
    menu.add_command(label="Restore Previous Layout", command=lambda: restore_previous_dashboard_layout(app))
    menu.add_command(label="Restore Defaults", command=lambda: restore_default_dashboard_layout(app))
    menu.tk_popup(app.dashboard_columns_button.winfo_rootx(), app.dashboard_columns_button.winfo_rooty() + app.dashboard_columns_button.winfo_height())


def show_dashboard_filters_menu(app):
    preferences = dashboard_preferences(app); active = preferences["filters"]
    menu = Menu(app.dashboard_filters_button, tearoff=False)
    groups = (
        ("Status", (("GOOD", "statuses"), ("BAD", "statuses"))),
        ("Features", (("Simulation", "features"), ("Trend", "features"), ("Alarm", "features"))),
        ("Data Type", tuple((data_type, "types") for data_type in sorted({str(getattr(tag, "data_type", "")).upper() for tag in getattr(app, "tags", []) if getattr(tag, "data_type", "")} | {"BOOL", "INT", "REAL"}))),
    )
    for group_name, entries in groups:
        submenu = Menu(menu, tearoff=False)
        for label, category in entries:
            key = label.upper() if category in ("statuses", "types") else label.casefold()
            checked = key in active[category]
            submenu.add_command(label=("☑ " if checked else "☐ ") + label, command=lambda cat=category, value=key: toggle_dashboard_filter(app, cat, value))
        menu.add_cascade(label=group_name, menu=submenu)
    menu.add_separator(); menu.add_command(label="Clear Filters", command=lambda: clear_dashboard_filters(app))
    menu.tk_popup(app.dashboard_filters_button.winfo_rootx(), app.dashboard_filters_button.winfo_rooty() + app.dashboard_filters_button.winfo_height())


def toggle_dashboard_filter(app, category, value):
    preferences = dashboard_preferences(app); values = preferences["filters"][category]
    if value in values: values.remove(value)
    else: values.append(value)
    app.settings.ui_preferences["dashboard_ui"] = normalize_dashboard_preferences(preferences)
    update_dashboard_filter_label(app); persist_dashboard_preferences(app); refresh_dashboard_table(app)


def clear_dashboard_filters(app):
    preferences = dashboard_preferences(app)
    preferences["filters"] = {"statuses": [], "features": [], "types": []}
    app.settings.ui_preferences["dashboard_ui"] = preferences
    update_dashboard_filter_label(app); persist_dashboard_preferences(app); refresh_dashboard_table(app)


def update_dashboard_filter_label(app):
    filters = dashboard_preferences(app)["filters"]
    count = sum(len(values) for values in filters.values())
    app.dashboard_filters_button.configure(text=f"Filters ({count})" if count else "Filters")


def create_dashboard_tab(app):
    if getattr(app, "_dashboard_structure_created", False): return
    app._dashboard_structure_created = True
    app.dashboard_events = deque(getattr(app, "dashboard_events", ()), maxlen=EVENT_LIMIT)
    preferences = dashboard_preferences(app)
    app._dashboard_sort_column = preferences["sort"]["column"]
    app._dashboard_sort_descending = preferences["sort"]["descending"]
    app._dashboard_selected_name = None
    app._dashboard_after_jobs = set()
    app._dashboard_last_render = {}

    root = ctk.CTkFrame(app.tab_dashboard, fg_color="#0f1720")
    root.pack(fill="both", expand=True, padx=4, pady=4)
    cards = ctk.CTkFrame(root, fg_color="transparent")
    cards.pack(fill="x", pady=(0, 6))
    app.dashboard_cards = {}
    titles = ("PLC", "Brand", "Project", "Total", "GOOD", "BAD", "Simulation", "Trend", "Alarm", "Communication", "Last read", "Read cycle")
    for index, title in enumerate(titles):
        card = ctk.CTkFrame(cards, fg_color=CARD_BG, border_width=1, border_color=BORDER, corner_radius=6)
        card.grid(row=index // 6, column=index % 6, padx=3, pady=3, sticky="nsew")
        cards.grid_columnconfigure(index % 6, weight=1)
        ctk.CTkLabel(card, text=title, text_color=COLORS["neutral"], font=("Arial", 10, "bold")).pack(pady=(5, 0))
        value = ctk.CTkLabel(card, text="—", font=("Arial", 14, "bold"))
        value.pack(pady=(0, 5))
        app.dashboard_cards[title] = value

    center = ctk.CTkFrame(root, fg_color="transparent")
    center.pack(fill="both", expand=True)
    app.dashboard_paned = PanedWindow(center, orient=HORIZONTAL, bg="#0f1720", bd=0, sashwidth=6, sashrelief="flat")
    app.dashboard_paned.pack(fill="both", expand=True)
    left = ctk.CTkFrame(app.dashboard_paned, fg_color=CARD_BG, border_width=1, border_color=BORDER)
    right = ctk.CTkFrame(app.dashboard_paned, width=330, fg_color=CARD_BG, border_width=1, border_color=BORDER)
    app.dashboard_paned.add(left, minsize=500, stretch="always")
    app.dashboard_paned.add(right, minsize=280, stretch="never")
    app.dashboard_paned.bind("<ButtonRelease-1>", lambda _event: capture_dashboard_splitter(app), add="+")
    app.schedule_job(0, lambda: restore_dashboard_splitter(app))

    controls = ctk.CTkFrame(left, fg_color="transparent")
    controls.pack(fill="x", padx=6, pady=5)
    app.dashboard_search_entry = ctk.CTkEntry(controls, width=240, placeholder_text="Name, address or comment")
    app.dashboard_search_entry.pack(side="left", padx=3)
    app.dashboard_search_entry.bind("<KeyRelease>", lambda _e: debounce(app, "dashboard_search", 150, lambda: refresh_dashboard_table(app)))
    ctk.CTkButton(controls, text="×", width=30, command=lambda: clear_dashboard_search(app)).pack(side="left", padx=2)
    app.dashboard_filters_button = ctk.CTkButton(controls, text="Filters", width=82, command=lambda: show_dashboard_filters_menu(app))
    app.dashboard_filters_button.pack(side="left", padx=3); update_dashboard_filter_label(app)
    app.dashboard_columns_button = ctk.CTkButton(controls, text="Columns", width=76, command=lambda: show_dashboard_columns_menu(app))
    app.dashboard_columns_button.pack(side="left", padx=3)
    app.dashboard_compact_button = ctk.CTkButton(controls, text="Compact View", width=115, command=lambda: toggle_dashboard_compact_view(app))
    app.dashboard_compact_button.pack(side="left", padx=3)
    app.dashboard_count_label = ctk.CTkLabel(controls, text="No dashboard tags")
    app.dashboard_count_label.pack(side="left", padx=8)
    app.tab_dashboard.bind("<Control-f>", lambda _event: focus_dashboard_search(app))
    app.tab_dashboard.bind("<Escape>", lambda _event: clear_dashboard_search(app))

    # Treeview columns remain user-resizable.  Stretch is disabled so Tk does
    # not squeeze them to the viewport; the horizontal scrollbar handles it.
    columns = DASHBOARD_COLUMNS
    table_frame = ctk.CTkFrame(left, fg_color="transparent")
    table_frame.pack(fill="both", expand=True, padx=4, pady=(0,4))
    table_frame.grid_rowconfigure(0, weight=1); table_frame.grid_columnconfigure(0, weight=1)
    app.dashboard_tag_table = ttk.Treeview(table_frame, columns=columns, show="headings", height=13)
    for definition in COLUMN_REGISTRY:
        app.dashboard_tag_table.column(definition.key, width=definition.default_width, minwidth=definition.minimum_width, stretch=False, anchor="w" if definition.key in ("name","comment") else "center")
    apply_dashboard_column_layout(app)
    y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=app.dashboard_tag_table.yview)
    x_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=app.dashboard_tag_table.xview)
    app.dashboard_tag_table.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
    app.dashboard_tag_table.grid(row=0,column=0,sticky="nsew"); y_scroll.grid(row=0,column=1,sticky="ns"); x_scroll.grid(row=1,column=0,sticky="ew")
    app.dashboard_empty_label = ctk.CTkLabel(table_frame, text="", fg_color="#f5f5f5", text_color="#475569")
    app.dashboard_tag_table.bind("<<TreeviewSelect>>", lambda _e: refresh_dashboard_detail(app))
    app.dashboard_tag_table.bind("<Double-1>", lambda event: dashboard_table_double_click(app, event))
    app.dashboard_tag_table.bind("<ButtonRelease-1>", lambda event: dashboard_heading_release(app, event), add="+")
    app.dashboard_tag_table.bind("<Button-3>", lambda event: show_dashboard_context_menu(app, event))
    app.dashboard_tag_table.bind("<Key>", lambda event: handle_dashboard_key(app, event))
    treeview_tag_comment_tooltip(
        app.dashboard_tag_table,
        lambda row: next(
            (tag for tag in app._dashboard_visible_tags if getattr(app, "_dashboard_row_ids", {}).get(tag.name) == row),
            None,
        ),
    )
    app._dashboard_visible_tags = []

    detail_scroll = ctk.CTkScrollableFrame(right, fg_color="transparent", corner_radius=0)
    detail_scroll.pack(fill="both", expand=True)
    ctk.CTkLabel(detail_scroll, text="SELECTED TAG", font=("Arial", 12, "bold"), text_color=COLORS["cyan"]).pack(pady=(8,3))
    app.dashboard_detail_labels = {}
    sections = {
        "GENERAL": ("Name","Comment","Address","Data Type","Direction"),
        "VALUES": ("Effective value","PLC value","Simulated value"),
        "CONFIGURATION": ("Simulation","Trend","Alarm","Dashboard"),
        "DIAGNOSTICS": ("Source","Quality","Last update"),
    }
    for section, fields in sections.items():
        ctk.CTkLabel(detail_scroll, text=section, font=("Arial", 10, "bold"), text_color=COLORS["neutral"], anchor="w").pack(fill="x", padx=10, pady=(5,1))
        for field in fields:
            label = ctk.CTkLabel(detail_scroll, text=f"{field}: —", anchor="w", justify="left", wraplength=285)
            label.pack(fill="x", padx=10, pady=1); app.dashboard_detail_labels[field] = label
            if field == "Name":
                tag_comment_tooltip(label, lambda: selected_dashboard_tag(app))
    app.dashboard_detail_indicator = ctk.CTkLabel(detail_scroll, text="—", font=("Arial", 24, "bold"), text_color=COLORS["neutral"])
    app.dashboard_detail_indicator.pack(pady=5)
    nav = ctk.CTkFrame(detail_scroll, fg_color="transparent"); nav.pack(fill="x", padx=6, pady=4)
    for text, command in (("Tag Manager",lambda: app.tabs.set("Tag Manager")),("Digital",lambda: app.tabs.set("Entradas Digitais")),("Analog",lambda: app.tabs.set("Entradas Analógicas"))):
        ctk.CTkButton(nav, text=text, width=100, command=command).pack(side="left", padx=2)

    lower = ctk.CTkFrame(root, fg_color="transparent"); lower.pack(fill="x", pady=(6,0))
    app.dashboard_panel_labels = {}
    panels = ("Communication", "Alarms", "Trends", "Simulation / Project")
    for column, title in enumerate(panels):
        panel = ctk.CTkFrame(lower, fg_color=CARD_BG, border_width=1, border_color=BORDER)
        panel.grid(row=0, column=column, padx=3, sticky="nsew"); lower.grid_columnconfigure(column, weight=1)
        ctk.CTkLabel(panel, text=title, font=("Arial", 11, "bold"), text_color=COLORS["cyan"]).pack(pady=(5,1))
        label = ctk.CTkLabel(panel, text="—", justify="left", font=("Arial", 10)); label.pack(padx=6, pady=2)
        app.dashboard_panel_labels[title] = label
        button_row=ctk.CTkFrame(panel,fg_color="transparent");button_row.pack(pady=(1,5))
        actions={
            "Communication":(("Tags",lambda:app.tabs.set("Tag Manager")),),
            "Alarms":(("Open",lambda:app.tabs.set("Alarmes")),),
            "Trends":(("Open",lambda:app.tabs.set("Trends")),("Start",lambda:_trend_action(app,True)),("Stop",lambda:_trend_action(app,False))),
            "Simulation / Project":(("Digital",lambda:app.tabs.set("Entradas Digitais")),("Analog",lambda:app.tabs.set("Entradas Analógicas")),("Stop all",lambda:stop_all_simulations(app)),("Save",app.save_project),("Save as",app.save_project_as),("Folder",lambda:open_project_folder(app))),
        }[title]
        for text,command in actions:ctk.CTkButton(button_row,text=text,width=58,height=24,command=command).pack(side="left",padx=1)

    event_frame = ctk.CTkFrame(root, fg_color=CARD_BG, border_width=1, border_color=BORDER)
    event_frame.pack(fill="x", pady=(6,0))
    app.dashboard_event_table = ttk.Treeview(event_frame, columns=("time","severity","event","detail"), show="headings", height=4)
    for col, width in (("time",80),("severity",80),("event",180),("detail",600)):
        app.dashboard_event_table.heading(col,text=col.title()); app.dashboard_event_table.column(col,width=width,anchor="w")
    app.dashboard_event_table.pack(fill="x", padx=5, pady=5)
    record_dashboard_event(app, "Dashboard ready")
    update_dashboard(app)
    _schedule_dashboard(app)


def _schedule_dashboard(app):
    if getattr(app, "is_closing", False) or getattr(app, "_shutdown_started", False): return
    job = None
    def run():
        app._dashboard_after_jobs.discard(job)
        if getattr(app, "is_closing", False): return
        update_dashboard(app); _schedule_dashboard(app)
    job = app.schedule_job(DASHBOARD_REFRESH_MS, run)
    if job is not None: app._dashboard_after_jobs.add(job)


def cancel_dashboard_callbacks(app):
    for job in tuple(getattr(app, "_dashboard_after_jobs", ())):
        try: app.cancel_job(job)
        except Exception: pass
    getattr(app, "_dashboard_after_jobs", set()).clear()


def reset_dashboard_project_state(app):
    """Discard project-scoped identity/snapshot state, preserving user layout."""
    app._dashboard_generation = getattr(app,"_dashboard_generation",0)+1
    app._dashboard_selected_name=None
    app._dashboard_row_ids={}; app._dashboard_row_values={}; app._dashboard_row_order=()
    app._dashboard_visible_tags=[]
    app._dashboard_detail_static_signature=None; app._dashboard_detail_dynamic_signature=None
    table=getattr(app,"dashboard_tag_table",None)
    if table is not None:
        children=table.get_children()
        if children: table.delete(*children)
    clear_dashboard_detail(app)


def clear_dashboard_search(app):
    app.dashboard_search_entry.delete(0,"end"); refresh_dashboard_table(app)


def focus_dashboard_search(app):
    app.dashboard_search_entry.focus_set(); app.dashboard_search_entry.select_range(0, "end")
    return "break"


def sort_dashboard(app, column):
    if app._dashboard_sort_column == column: app._dashboard_sort_descending = not app._dashboard_sort_descending
    else: app._dashboard_sort_column, app._dashboard_sort_descending = column, False
    if getattr(app, "settings", None) is not None:
        preferences = dashboard_preferences(app)
        preferences["sort"] = {"column": app._dashboard_sort_column, "descending": app._dashboard_sort_descending}
        app.settings.ui_preferences["dashboard_ui"] = preferences
        persist_dashboard_preferences(app)
    if hasattr(app, "dashboard_tag_table"):
        configure_dashboard_headings(app.dashboard_tag_table, lambda key: sort_dashboard(app, key), app._dashboard_sort_column, app._dashboard_sort_descending)
    refresh_dashboard_table(app)


def _identified_display_column(table, x):
    identifier = table.identify_column(x)
    try: index = int(identifier.lstrip("#")) - 1
    except (AttributeError, ValueError): return None
    display = table.cget("displaycolumns")
    if isinstance(display, str): display = table.tk.splitlist(display)
    if display == ("#all",) or display == "#all": display = DASHBOARD_COLUMNS
    return display[index] if 0 <= index < len(display) else None


def capture_dashboard_column_widths(app):
    preferences = dashboard_preferences(app)
    for column in DASHBOARD_COLUMNS:
        preferences["full_layout"]["widths"][column] = int(app.dashboard_tag_table.column(column, "width"))
    app.settings.ui_preferences["dashboard_ui"] = normalize_dashboard_preferences(preferences)
    persist_dashboard_preferences(app)


def dashboard_heading_release(app, event):
    if app.dashboard_tag_table.identify_region(event.x, event.y) == "separator":
        app.schedule_job(0, lambda: capture_dashboard_column_widths(app))


def restore_dashboard_splitter(app):
    paned=app.dashboard_paned; width=max(1,paned.winfo_width())
    ratio=dashboard_preferences(app)["splitter"]
    try: paned.sash_place(0,max(500,min(width-280,int(width*ratio))),0)
    except TclError: pass


def capture_dashboard_splitter(app):
    paned=app.dashboard_paned; width=max(1,paned.winfo_width())
    try: ratio=paned.sash_coord(0)[0]/width
    except TclError:return
    preferences=dashboard_preferences(app); preferences["splitter"]=ratio
    app.settings.ui_preferences["dashboard_ui"]=normalize_dashboard_preferences(preferences)
    persist_dashboard_preferences(app)


def dashboard_table_double_click(app, event):
    table = app.dashboard_tag_table
    if table.identify_region(event.x, event.y) == "separator":
        column = _identified_display_column(table, event.x)
        if column: auto_fit_dashboard_column(app, column)
        return "break"
    open_selected_dashboard_tag(app)


def _source(runtime, brand):
    if runtime is None or runtime.source is None: return "Unknown"
    source = str(getattr(runtime.source, "value", runtime.source))
    return "Internal Simulator" if brand == "Simulator" and source == "PLC" else source.title()


def refresh_dashboard_table(app):
    tags = get_dashboard_tags(app)
    query = app.dashboard_search_entry.get() if hasattr(app,"dashboard_search_entry") else ""
    quick = app.dashboard_filter_menu.get() if hasattr(app,"dashboard_filter_menu") else "All"
    if hasattr(app, "dashboard_filters_button"):
        tags = filter_dashboard_population(tags, query, dashboard_preferences(app)["filters"], app.tag_runtime)
    else:
        tags = filter_dashboard_tags(tags, query, quick, app.tag_runtime)
    if quick == "Alarm active":
        active = {a.get("source") for a in getattr(app,"alarms",[]) if a.get("active")}
        tags = [tag for tag in tags if tag.name in active]
    alarm_names = {a.get("source") for a in getattr(app,"alarms",[]) if a.get("active")}
    brand=connection_brand(app)
    filter_state = dashboard_preferences(app)["filters"] if hasattr(app,"dashboard_filters_button") else {"legacy":quick}
    criteria=(query,repr(filter_state),app._dashboard_sort_column,app._dashboard_sort_descending)
    if app._dashboard_sort_column=="value" and criteria==getattr(app,"_dashboard_view_criteria",None):
        by_name={tag.name:tag for tag in tags}; prior=getattr(app,"_dashboard_row_order",())
        tags=[by_name.pop(name) for name in prior if name in by_name]+sort_dashboard_population(by_name.values(),"name",False,app.tag_runtime)
    else:
        tags=sort_dashboard_population(tags, app._dashboard_sort_column, app._dashboard_sort_descending, app.tag_runtime)
    app._dashboard_view_criteria=criteria
    selected = app._dashboard_selected_name
    table = app.dashboard_tag_table
    row_ids = getattr(app, "_dashboard_row_ids", {})
    next_id = getattr(app, "_dashboard_next_row_id", 0)
    row_values = getattr(app, "_dashboard_row_values", {})
    desired_names = {tag.name for tag in tags}
    desired_order = tuple(tag.name for tag in tags)
    order_changed = desired_order != getattr(app, "_dashboard_row_order", ())
    for name, item in tuple(row_ids.items()):
        if name not in desired_names:
            table.delete(item); row_ids.pop(name, None); row_values.pop(name, None)
    for index, tag in enumerate(tags):
        runtime = app.tag_runtime.get(tag.name); valid = bool(runtime and runtime.valid); value = runtime.value if valid else "—"
        displayed=("● GOOD" if valid else "● BAD",getattr(tag,"name","") or "—",getattr(tag,"address","") or "—",getattr(tag,"comment","") or "",getattr(tag,"data_type","") or "—",value,_source(runtime,brand),"ACTIVE" if tag.name in alarm_names else "Normal","ON" if getattr(tag,"enabled_trend",False) else "Off")
        item = row_ids.get(tag.name)
        if item is None:
            item = f"dashboard-row-{next_id}"; next_id += 1
            table.insert("","end",iid=item,values=displayed); row_ids[tag.name]=item; row_values[tag.name]=displayed
        else:
            if row_values.get(tag.name) != displayed:
                previous=row_values.get(tag.name,())
                for column,old,new in zip(DASHBOARD_COLUMNS,previous,displayed):
                    if old != new: table.set(item,column,new)
                row_values[tag.name]=displayed
            if order_changed:
                table.move(item,"",index)
    app._dashboard_row_ids=row_ids; app._dashboard_next_row_id=next_id; app._dashboard_row_values=row_values
    app._dashboard_row_order=desired_order
    app._dashboard_visible_tags = tags
    selected_item = row_ids.get(selected)
    if selected is None and tags:
        selected_item=row_ids[tags[0].name]; app._dashboard_selected_name=tags[0].name
    if selected_item is not None and table.selection() != (selected_item,): table.selection_set(selected_item)
    elif selected_item is None and table.selection(): table.selection_remove(*table.selection())
    total = len(get_dashboard_tags(app))
    if tags:
        app.dashboard_count_label.configure(text=f"Showing {len(tags)} of {total} tags")
        if hasattr(app, "dashboard_empty_label"): app.dashboard_empty_label.place_forget()
    else:
        message = "No tags match the current search and filters." if total else "No dashboard-enabled tags."
        app.dashboard_count_label.configure(text=message)
        if hasattr(app, "dashboard_empty_label"):
            app.dashboard_empty_label.configure(text=message); app.dashboard_empty_label.place(relx=.5,rely=.45,anchor="center")
    refresh_dashboard_detail(app)


def refresh_dashboard_detail(app):
    selection = app.dashboard_tag_table.selection()
    if not selection:
        clear_dashboard_detail(app); return
    item = selection[0]
    tag = next((candidate for candidate in app._dashboard_visible_tags if getattr(app,"_dashboard_row_ids",{}).get(candidate.name) == item), None)
    if tag is None: return
    app._dashboard_selected_name = tag.name
    refresh_dashboard_detail_static(app, tag)
    refresh_dashboard_detail_dynamic(app, tag)


def selected_dashboard_tag(app):
    name = getattr(app, "_dashboard_selected_name", None)
    return next((tag for tag in getattr(app, "tags", []) if getattr(tag, "name", None) == name), None)


def refresh_dashboard_detail_static(app, tag):
    signature = tuple(getattr(tag, field, None) for field in ("name","comment","address","data_type","direction","enabled_sim","enabled_trend","enabled_alarm","enabled_dashboard"))
    if signature == getattr(app, "_dashboard_detail_static_signature", None): return
    app._dashboard_detail_static_signature = signature
    content = {"Name":getattr(tag,"name","—") or "—","Comment":getattr(tag,"comment","") or "—","Address":getattr(tag,"address","") or "—","Data Type":getattr(tag,"data_type","") or "—","Direction":getattr(tag,"direction","") or "—","Simulation":"Enabled" if getattr(tag,"enabled_sim",False) else "Disabled","Trend":"Enabled" if getattr(tag,"enabled_trend",False) else "Disabled","Alarm":"Enabled" if getattr(tag,"enabled_alarm",False) else "Disabled","Dashboard":"Enabled" if getattr(tag,"enabled_dashboard",False) else "Disabled"}
    for field,value in content.items(): app.dashboard_detail_labels[field].configure(text=f"{field}: {value}")


def refresh_dashboard_detail_dynamic(app, tag):
    runtime = app.tag_runtime.get(tag.name); valid = bool(runtime and runtime.valid); effective = runtime.value if valid else "—"
    plc = getattr(app,"_plc_values",{}).get(tag.name,"—"); simulated = getattr(app,"_simulated_values",{}).get(tag.name,"—")
    source = _source(runtime, connection_brand(app)); updated = time.strftime("%H:%M:%S",time.localtime(runtime.updated_at)) if valid and runtime.updated_at else "Never"
    signature=(effective,plc,simulated,source,valid,updated)
    if signature == getattr(app,"_dashboard_detail_dynamic_signature",None): return
    app._dashboard_detail_dynamic_signature=signature
    content = {"Effective value":effective,"PLC value":plc,"Simulated value":simulated,"Source":source,"Quality":"GOOD" if valid else "BAD","Last update":updated}
    for field,value in content.items(): app.dashboard_detail_labels[field].configure(text=f"{field}: {value}")
    if tag.data_type == "BOOL" and valid: app.dashboard_detail_indicator.configure(text="● ON" if bool(effective) else "● OFF",text_color=COLORS["green"] if bool(effective) else COLORS["red"])
    else: app.dashboard_detail_indicator.configure(text=str(effective),text_color=COLORS["cyan"] if valid else COLORS["neutral"])


def clear_dashboard_detail(app):
    app._dashboard_detail_static_signature=None; app._dashboard_detail_dynamic_signature=None
    for field,label in getattr(app,"dashboard_detail_labels",{}).items(): label.configure(text=f"{field}: —")
    if hasattr(app,"dashboard_detail_indicator"): app.dashboard_detail_indicator.configure(text="—",text_color=COLORS["neutral"])


def open_selected_dashboard_tag(app):
    name = getattr(app,"_dashboard_selected_name",None)
    tag = next((t for t in getattr(app,"tags",[]) if t.name == name),None)
    if tag is None: return
    if tag.data_type == "BOOL":
        from ui.digital_tab import refresh_digital_tab
        app._digital_selected_tag_name=name; app.tabs.set("Entradas Digitais"); refresh_digital_tab(app)
    else:
        from ui.analog_tab import refresh_analog_tab
        app._analog_selected_tag_name=name; app.tabs.set("Entradas Analógicas"); refresh_analog_tab(app)


def show_dashboard_context_menu(app, event):
    row = app.dashboard_tag_table.identify_row(event.y)
    if row:
        app.dashboard_tag_table.selection_set(row)
        name = next((name for name,item in getattr(app,"_dashboard_row_ids",{}).items() if item == row), None)
        if name: app._dashboard_selected_name=name
        refresh_dashboard_detail(app)
    tag = selected_dashboard_tag(app)
    if tag is None: return
    runtime = app.tag_runtime.get(tag.name); value = runtime.value if runtime and runtime.valid else ""
    menu = Menu(app.dashboard_tag_table, tearoff=False)
    for label, payload in (("Copy Name",tag.name),("Copy Address",getattr(tag,"address","")),("Copy Comment",getattr(tag,"comment","")),("Copy Value",value)):
        menu.add_command(label=label, command=lambda text=payload: copy_text(app.dashboard_tag_table,text))
    menu.add_separator()
    menu.add_command(label="Locate in Tag Manager", command=lambda: locate_dashboard_tag_in_manager(app))
    menu.add_command(label="Open in Trends", command=lambda: open_dashboard_tag_in_trends(app))
    menu.tk_popup(event.x_root,event.y_root)


def locate_dashboard_tag_in_manager(app):
    tag=selected_dashboard_tag(app)
    if tag is None:return
    app.ensure_tag_manager_tab(); app.tabs.set("Tag Manager")
    entry=app.tag_search_entry; entry.delete(0,"end"); entry.insert(0,tag.name)
    from ui.tag_manager import refresh_tag_table
    refresh_tag_table(app,view_only=True)
    children=app.tag_table.get_children()
    if children: app.tag_table.selection_set(children[0]); app.tag_table.focus(children[0]); app.tag_table.see(children[0])


def open_dashboard_tag_in_trends(app):
    tag=selected_dashboard_tag(app)
    if tag is None:return
    app.ensure_trend_tab(); app.tabs.set("Trends")
    entry=app.trend_search_entry; entry.delete(0,"end"); entry.insert(0,tag.name)
    from ui.trend_tab import bind_selected_trend, refresh_trend_selectors
    refresh_trend_selectors(app,reset_page=True)
    children=app.trend_table.get_children()
    if children: app.trend_table.selection_set(children[0]); app.trend_table.focus(children[0]); app.trend_table.see(children[0]); bind_selected_trend(app)


def handle_dashboard_key(app,event):
    key=getattr(event,"keysym","")
    if key in ("Up","Down","Prior","Next","Home","End"):
        move_selection(app.dashboard_tag_table,key); refresh_dashboard_detail(app); return "break"
    if key.lower()=="c" and getattr(event,"state",0)&0x4:
        tag=selected_dashboard_tag(app)
        if tag is not None: copy_text(app.dashboard_tag_table,tag.name)
        return "break"


def update_dashboard(app, last_message=None):
    if not hasattr(app,"dashboard_cards"): return
    if last_message: record_dashboard_event(app,last_message)
    values=dashboard_summary_values(app); connected=app.plc_service.is_connected(); brand=connection_brand(app); diagnostics=app.plc_service.diagnostics_snapshot(); project=os.path.basename(getattr(app,"project_path","") or "No project")
    for title,(value,color) in values.items():
        if title in app.dashboard_cards: app.dashboard_cards[title].configure(text=str(value),text_color=COLORS[color])
    population=get_dashboard_tags(app); stats=dashboard_statistics(population,app.tag_runtime)
    for title,key,color in (("Total","total","neutral"),("GOOD","good","green"),("BAD","bad","red"),("Simulation","simulation","amber"),("Trend","trend","cyan"),("Alarm","alarm","amber")):
        app.dashboard_cards[title].configure(text=str(stats[key]),text_color=COLORS[color])
    refresh_dashboard_table(app)
    alarm=dashboard_alarm_summary(app); trend_data=getattr(app,"trend_data",{"time":[],"tags":{}}); selected_trends=len(getattr(app,"trend_visible_tags",set())) if hasattr(app,"trend_visible_tags") else sum(v.get() for v in getattr(app,"trend_tag_vars",{}).values()) if hasattr(app,"trend_tag_vars") else 0
    app.dashboard_panel_labels["Communication"].configure(text=f"Driver: {diagnostics['brand'] or 'None'} · {'Connected' if connected else 'Disconnected'}\nReads: {diagnostics['read_success_count']} ok / {diagnostics['read_error_count']} err · avg {diagnostics['average_read_duration_ms']:.1f} ms · {_fmt_time(diagnostics['last_read_timestamp'])}\nWrites: {diagnostics['write_success_count']} ok / {diagnostics['write_error_count']} err · avg {diagnostics['average_write_duration_ms']:.1f} ms · {_fmt_time(diagnostics['last_write_timestamp'])}\nReconnects: {diagnostics['reconnect_count']}")
    app.dashboard_panel_labels["Alarms"].configure(text=f"Active: {alarm['active']} · Unack: {alarm['unacknowledged']} · High priority: {alarm['high_priority']}\nLatest: {alarm['latest'].get('source') if alarm['latest'] else 'None'} · Cleared: {alarm['latest_cleared'] or 'None'}")
    trend_times=trend_data.get('time',[]); latest_sample=_fmt_time(getattr(app,'trend_start_time',0)+(trend_times[-1] if trend_times else 0)) if trend_times else "Never"
    app.dashboard_panel_labels["Trends"].configure(text=f"{'ON' if getattr(app,'trend_running',False) else 'OFF'} · Selected: {selected_trends}\nBuffered points: {len(trend_times)} · Duration: {trend_times[-1] if trend_times else 0}s · Latest: {latest_sample}")
    active_profiles=sum(bool(v) for v in getattr(app,"analog_profile_running",{}).values()); pulses=len(getattr(app,"pending_pulse_callbacks",{})); active_digital=sum(1 for tag in getattr(app,"tags",[]) if tag.data_type=="BOOL" and tag.name in getattr(app,"_simulated_values",{})); dirty="DIRTY" if getattr(app,"_project_dirty",False) else "CLEAN"
    connection=_connection_summary(app,brand); saved=_fmt_time(getattr(app,"_last_project_save_timestamp",None)); path=getattr(app,"project_path",None) or "No project file"
    app.dashboard_panel_labels["Simulation / Project"].configure(text=f"Digital active: {active_digital} · Pulses: {pulses} · Analog profiles: {active_profiles} · Internal: {'connected' if brand=='Simulator' and connected else 'off'}\n{project} · {dirty} · v{APP_VERSION}\n{connection} · Saved: {saved}\n{path}")


def refresh_dashboard(app): update_dashboard(app)


def _fmt_time(timestamp): return time.strftime("%H:%M:%S",time.localtime(timestamp)) if timestamp else "Never"


def _connection_summary(app,brand):
    if brand=="Simulator":return "Internal Simulator"
    if brand=="Siemens":
        return f"{connection_value(app,'ip')} · Rack {connection_value(app,'rack')} Slot {connection_value(app,'slot')}"
    return f"{connection_value(app,'ip')} · {brand}"


def record_dashboard_event(app, message, severity="INFO", detail=""):
    message=str(message).strip()
    if not message:return
    if not hasattr(app,"dashboard_events"): app.dashboard_events=deque(maxlen=EVENT_LIMIT)
    if not isinstance(app.dashboard_events,deque): app.dashboard_events=deque(app.dashboard_events,maxlen=EVENT_LIMIT)
    lower=message.casefold()
    if any(word in lower for word in ("error","erro","failed","alarm active")): severity="ERROR"
    elif any(word in lower for word in ("warning","degraded")): severity="WARN"
    app.dashboard_events.append((_fmt_time(time.time()),severity,message,detail))
    render_dashboard_events(app)


def clear_dashboard_events(app): app.dashboard_events=deque(maxlen=EVENT_LIMIT); render_dashboard_events(app)


def render_dashboard_events(app):
    table=getattr(app,"dashboard_event_table",None)
    if table is None:return
    table.delete(*table.get_children())
    for event in list(app.dashboard_events)[-20:]:
        if len(event)==2:event=(event[0],"INFO",event[1],"")
        table.insert("","end",values=event)


def stop_all_simulations(app):
    if not messagebox.askyesno("Stop simulations","Stop all pulses and analog profiles?"):return
    for job in tuple(getattr(app,"pending_pulse_callbacks",{}).values()): app.cancel_job(job)
    getattr(app,"pending_pulse_callbacks",{}).clear()
    manager=getattr(app,"analog_simulation_manager",None)
    if manager is not None: manager.stop_all()
    else:
        for index in tuple(getattr(app,"analog_profile_running",{})): app.analog_profile_running[index]=False
    record_dashboard_event(app,"All simulations stopped","WARN")


def _trend_action(app, start):
    app.ensure_trend_tab()
    from ui.trend_tab import start_trend, stop_trend
    (start_trend if start else stop_trend)(app)


def open_project_folder(app):
    path=os.path.dirname(getattr(app,"project_path","") or "")
    if path and os.path.isdir(path): subprocess.Popen(["xdg-open",path],start_new_session=True)
