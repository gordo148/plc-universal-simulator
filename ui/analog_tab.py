import logging
import time

import customtkinter as ctk
from tkinter import ttk
from ui.analog_profiles import start_profile, stop_profile
from ui.scrollable_frame import widget_exists


LOGGER = logging.getLogger(__name__)
ANALOG_BATCH_SIZE = 10
PAGE_SIZES = (25, 50, 100)


def create_analog_tab_structure(app):
    """Create persistent Analog controls exactly once."""
    if getattr(app, "_analog_structure_initialized", False):
        return
    started = time.perf_counter()
    controls = ctk.CTkFrame(app.tab_analog)
    controls.pack(fill="x", padx=10, pady=(10, 0))
    ctk.CTkLabel(controls, text="Search").pack(side="left", padx=5)
    app.analog_search_entry = ctk.CTkEntry(controls, width=260)
    app.analog_search_entry.pack(side="left", padx=5)
    app.analog_search_entry.bind("<KeyRelease>", lambda _event: refresh_analog_tab(app, reset_page=True))
    ctk.CTkLabel(controls, text="Tags per page").pack(side="left", padx=5)
    app.analog_page_size_menu = ctk.CTkOptionMenu(
        controls, values=[str(size) for size in PAGE_SIZES], width=75,
        command=lambda _value: refresh_analog_tab(app),
    )
    app.analog_page_size_menu.set("50")
    app.analog_page_size_menu.pack(side="left", padx=5)
    app.analog_previous_button = ctk.CTkButton(
        controls, text="Previous", width=90, command=lambda: change_analog_page(app, -1)
    )
    app.analog_previous_button.pack(side="left", padx=5)
    app.analog_next_button = ctk.CTkButton(
        controls, text="Next", width=90, command=lambda: change_analog_page(app, 1)
    )
    app.analog_next_button.pack(side="left", padx=5)
    app.analog_loading_label = ctk.CTkLabel(controls, text="Analog signals not loaded")
    app.analog_loading_label.pack(side="left", padx=15)
    app.analog_page = 0
    app.analog_row_pool = []
    app._analog_after_jobs = set()
    app._analog_rebuilding = False
    app._analog_structure_initialized = True
    _create_analog_master_detail(app)
    LOGGER.info(
        "Analog tab structure created: widgets_created=36 callbacks_registered=4 structure_time_ms=%.3f",
        (time.perf_counter() - started) * 1000,
    )


create_analog_tab = create_analog_tab_structure


def _create_analog_master_detail(app):
    body = ctk.CTkFrame(app.tab_analog)
    body.pack(fill="both", expand=True, padx=10, pady=10)
    table_frame = ctk.CTkFrame(body)
    table_frame.pack(fill="both", expand=True)
    columns = ("address", "name", "type", "value", "profile")
    table = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
    for column, title, width in (
        ("address", "Address", 120), ("name", "Name", 260),
        ("type", "Type", 80), ("value", "Current value", 120),
        ("profile", "Setpoint / Profile", 160),
    ):
        table.heading(column, text=title)
        table.column(column, width=width, anchor="center" if column != "name" else "w")
    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
    table.configure(yscrollcommand=scrollbar.set)
    table.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    editor_host = ctk.CTkFrame(body)
    editor_host.pack(fill="x", pady=(8, 0))
    app.analog_scroll = editor_host
    editor_row = create_analog_row_widgets(app)
    editor_row["frame"].pack(fill="x")
    table.bind("<<TreeviewSelect>>", lambda _event: _bind_selected_analog(app))
    app.analog_table = table
    app.analog_table_scrollbar = scrollbar
    app.analog_editor = editor_row
    app.analog_row_pool = [editor_row]
    app._analog_table_tags = []
    app._analog_selected_tag_name = None


def _bind_selected_analog(app):
    selection = app.analog_table.selection()
    if not selection:
        return
    position = app.analog_table.index(selection[0])
    if position >= len(app._analog_table_tags):
        return
    tag = app._analog_table_tags[position]
    app._analog_selected_tag_name = tag.name
    app.analog_controls[:] = []
    app.analog_tags[:] = []
    app.analog_profile_directions.clear()
    bind_analog_row(app, app.analog_editor, 0, tag)
    app.analog_controls.append(app.analog_editor)
    app.analog_tags.append(tag)


def cancel_analog_refresh(app):
    jobs = getattr(app, "_analog_after_jobs", set())
    for job in tuple(jobs):
        try:
            app.cancel_job(job)
        except Exception:
            pass
    if jobs:
        LOGGER.info("Analog lazy refresh cancellation jobs=%d", len(jobs))
    jobs.clear()
    app._analog_rebuilding = False


def change_analog_page(app, offset):
    app.analog_page = max(0, getattr(app, "analog_page", 0) + offset)
    refresh_analog_tab(app)


def refresh_analog_visible_rows(app, reset_page=False):
    refresh_started = time.perf_counter()
    from ui.tag_manager import get_input_analog_tags

    cancel_analog_refresh(app)
    if reset_page:
        app.analog_page = 0
    query = app.analog_search_entry.get().strip().casefold()
    tags = [
        tag for tag in get_input_analog_tags(app)
        if not query or query in tag.name.casefold() or query in tag.address.casefold()
    ]
    page_size_widget = getattr(app, "analog_page_size_menu", None)
    page_size = int(page_size_widget.get()) if page_size_widget is not None else 50
    page_count = max(1, (len(tags) + page_size - 1) // page_size)
    app.analog_page = min(getattr(app, "analog_page", 0), page_count - 1)
    start = app.analog_page * page_size
    page_tags = tags[start:start + page_size]
    app._analog_rebuilding = True
    if hasattr(app, "analog_table"):
        begin_analog_refresh(app, page_tags)
        _refresh_analog_table(app, tags, page_count, start, page_tags, refresh_started)
        return
    LOGGER.info("Analog lazy refresh start total=%d page=%d", len(tags), app.analog_page + 1)
    begin_analog_refresh(app, page_tags)
    app.analog_loading_label.configure(text=f"Generating signals: 0 / {len(page_tags)}")

    def schedule(callback):
        if getattr(app, "is_closing", False):
            return
        job = None
        def run():
            app._analog_after_jobs.discard(job)
            if getattr(app, "is_closing", False):
                return
            callback()
        job = app.schedule_job(1, run)
        if job is not None:
            app._analog_after_jobs.add(job)

    def finish():
        if getattr(app, "is_closing", False) or not widget_exists(app.analog_loading_label):
            return
        app.analog_controls[:] = []
        app.analog_tags[:] = []
        app.analog_profile_directions.clear()
        for local_index, row in enumerate(app.analog_row_pool):
            if local_index < len(page_tags):
                bind_analog_row(app, row, local_index, page_tags[local_index])
                row["frame"].pack(fill="x", padx=10, pady=10)
                app.analog_controls.append(row)
                app.analog_tags.append(page_tags[local_index])
            else:
                row["current_tag_index"] = None
                row["tag"] = None
                row["frame"].pack_forget()
        finish_analog_refresh(app)
        app._analog_rebuilding = False
        getattr(app, "_dirty_tabs", set()).discard("Entradas Analógicas")
        pending_profiles = getattr(app, "_pending_analog_profiles", None)
        if pending_profiles is not None:
            del app._pending_analog_profiles
            from ui.project_config import _restore_analog_profiles
            _restore_analog_profiles(app, pending_profiles)
        elif getattr(app, "_analog_profile_cache", None):
            from ui.project_config import _restore_analog_profiles
            _restore_analog_profiles(app, app._analog_profile_cache.values())
        app.analog_loading_label.configure(
            text=f"Page {app.analog_page + 1} of {page_count} · {start + 1 if page_tags else 0}-{start + len(page_tags)} of {len(tags)}"
        )
        app.analog_previous_button.configure(state="normal" if app.analog_page else "disabled")
        app.analog_next_button.configure(state="normal" if app.analog_page + 1 < page_count else "disabled")
        refresh_button = getattr(app, "tag_update_signals_button", None)
        if refresh_button is not None:
            refresh_button.configure(state="normal")
        LOGGER.info(
            "Analog page refreshed: page=%d visible=%d total=%d",
            app.analog_page + 1, len(page_tags), len(tags),
        )

    def grow_pool():
        if getattr(app, "is_closing", False) or not widget_exists(app.analog_loading_label):
            return
        pool = getattr(app, "analog_row_pool", [])
        old_size = len(pool)
        target = min(len(page_tags), len(pool) + ANALOG_BATCH_SIZE)
        while len(pool) < target:
            pool.append(create_analog_row_widgets(app))
        if len(pool) != old_size:
            LOGGER.info("Analog row pool expanded: old=%d new=%d", old_size, len(pool))
        app.analog_row_pool = pool
        app.analog_loading_label.configure(
            text=f"Generating signals: {min(len(pool), len(page_tags))} / {len(page_tags)}"
        )
        if len(pool) < len(page_tags):
            schedule(grow_pool)
        else:
            finish()

    if len(getattr(app, "analog_row_pool", [])) < len(page_tags):
        schedule(grow_pool)
    else:
        finish()


refresh_analog_tab = refresh_analog_visible_rows


def _refresh_analog_table(app, tags, page_count, start, visible, refresh_started):
    selected = getattr(app, "_analog_selected_tag_name", None)
    table = app.analog_table
    table.delete(*table.get_children())
    app._analog_table_tags = list(visible)
    selected_item = None
    for tag in visible:
        value = app.tag_runtime.get_value(tag.name, 0)
        settings = getattr(app, "_analog_profile_cache", {}).get(tag.name, {})
        item = table.insert("", "end", values=(
            tag.address, tag.name, tag.data_type, value,
            settings.get("mode", "Manual") if tag.enabled_sim else "PLC read-only",
        ))
        if tag.name == selected:
            selected_item = item
    app._analog_rebuilding = False
    app._dirty_tabs.discard("Entradas Analógicas")
    app.analog_loading_label.configure(text=f"Page {app.analog_page + 1} of {page_count} · {start + 1 if visible else 0}-{start + len(visible)} of {len(tags)}")
    app.analog_previous_button.configure(state="normal" if app.analog_page else "disabled")
    app.analog_next_button.configure(state="normal" if app.analog_page + 1 < page_count else "disabled")
    if selected_item is None and table.get_children():
        selected_item = table.get_children()[0]
    if selected_item is not None:
        table.selection_set(selected_item)
        _bind_selected_analog(app)
    LOGGER.info(
        "Analog tab generation: tags_total=%d visible_rows=%d widgets_created=0 callbacks_registered=0 row_creation_time_ms=0 layout_time_ms=%.3f total_time_ms=%.3f",
        len(tags), len(visible), 0.0, (time.perf_counter() - refresh_started) * 1000,
    )


def update_analog_table_values(app):
    table = getattr(app, "analog_table", None)
    if table is None or not widget_exists(table):
        return
    for item, tag in zip(table.get_children(), app._analog_table_tags):
        values = list(table.item(item, "values"))
        values[3] = app.tag_runtime.get_value(tag.name, 0)
        table.item(item, values=values)
    _bind_selected_analog(app)


def begin_analog_refresh(app, tags):
    """Save visible settings; persistent pooled widgets are never destroyed."""
    LOGGER.info("Analog refresh started")
    cache = getattr(app, "_analog_profile_cache", {})
    for index, item in enumerate(app.analog_controls):
        if index >= len(app.analog_tags) or not item.get("interactive", True):
            continue
        tag_name = app.analog_tags[index].name
        cache[tag_name] = {
            "tag": tag_name,
            "mode": item["profile_mode"].get(),
            "min": item["min_entry"].get(),
            "max": item["max_entry"].get(),
            "step": item["step_entry"].get(),
            "interval_ms": item["interval_entry"].get(),
        }
    app._analog_profile_cache = cache
    app.analog_controls.clear()
    app.analog_tags.clear()
    app.analog_profile_running.clear()
    app.analog_profile_directions.clear()
    LOGGER.info("Analog refresh tags received count=%d", len(tags))


def finish_analog_refresh(app):
    LOGGER.info("Analog refresh completed widgets=%d", len(app.analog_controls))


def on_slider_changed(app, index, value):
    if getattr(app, "is_rebuilding", False) or getattr(app, "_analog_rebuilding", False):
        LOGGER.debug("Analog slider callback ignored during rebuild index=%d", index)
        return
    app.update_analog(index, value)


def on_profile_start(app, index):
    if getattr(app, "is_rebuilding", False) or getattr(app, "_analog_rebuilding", False):
        return
    start_profile(app, index)


def on_profile_stop(app, index):
    if getattr(app, "is_rebuilding", False) or getattr(app, "_analog_rebuilding", False):
        return
    stop_profile(app, index)


def create_analog_row_widgets(app):
    """Allocate one reusable heavy Analog row without assigning a tag."""
    card = ctk.CTkFrame(app.analog_scroll, corner_radius=15)
    top = ctk.CTkFrame(card)
    top.pack(fill="x", padx=10, pady=8)
    address = ctk.CTkLabel(top, text="", width=100, font=("Arial", 14, "bold"))
    address.pack(side="left", padx=8)
    protocol_address = ctk.CTkLabel(top, text="", width=120, text_color="gray")
    protocol_address.pack(side="left", padx=8)
    name_widget = ctk.CTkEntry(top, width=250)
    name_widget.pack(side="left", padx=8)
    value_label = ctk.CTkLabel(top, text="0 RAW", width=110, font=("Arial", 18, "bold"), text_color="cyan")
    value_label.pack(side="left", padx=8)
    live = ctk.CTkLabel(top, text="0", width=80, font=("Arial", 18, "bold"))
    live.pack(side="left", padx=8)
    readonly = ctk.CTkLabel(top, text="PLC READ-ONLY", width=130, text_color="gray")
    profile_status = ctk.CTkLabel(top, text="MANUAL", width=100, text_color="gray")
    profile_status.pack(side="left", padx=8)
    slider = ctk.CTkSlider(card, from_=0, to=27648, width=750)
    slider.pack(padx=20, pady=12)
    profile = ctk.CTkFrame(card)
    profile.pack(fill="x", padx=10, pady=8)
    ctk.CTkLabel(profile, text="Modo").pack(side="left", padx=5)
    profile_mode = ctk.CTkOptionMenu(profile, values=["Manual", "Ramp", "Random", "Step"], width=100)
    profile_mode.pack(side="left", padx=5)
    ctk.CTkLabel(profile, text="Min").pack(side="left", padx=5)
    min_entry = ctk.CTkEntry(profile, width=80); min_entry.pack(side="left", padx=5)
    ctk.CTkLabel(profile, text="Max").pack(side="left", padx=5)
    max_entry = ctk.CTkEntry(profile, width=80); max_entry.pack(side="left", padx=5)
    ctk.CTkLabel(profile, text="Step").pack(side="left", padx=5)
    step_entry = ctk.CTkEntry(profile, width=80); step_entry.pack(side="left", padx=5)
    ctk.CTkLabel(profile, text="Intervalo ms").pack(side="left", padx=5)
    interval_entry = ctk.CTkEntry(profile, width=90); interval_entry.pack(side="left", padx=5)
    start_button = ctk.CTkButton(profile, text="Start", width=90); start_button.pack(side="left", padx=8)
    stop_button = ctk.CTkButton(profile, text="Stop", width=90); stop_button.pack(side="left", padx=8)
    return {
        "frame": card, "top": top, "profile_frame": profile,
        "address_label": address, "protocol_address_label": protocol_address,
        "interactive": True, "name_entry": name_widget, "slider": slider,
        "value_label": value_label, "live": live, "readonly_label": readonly,
        "profile_mode": profile_mode, "profile_status": profile_status,
        "min_entry": min_entry, "max_entry": max_entry,
        "step_entry": step_entry, "interval_entry": interval_entry,
        "start_button": start_button, "stop_button": stop_button,
        "current_tag_index": None, "tag": None,
    }


def _replace_entry(entry, value):
    if hasattr(entry, "delete"):
        entry.delete(0, "end")
    entry.insert(0, str(value))


def _show(widget, **pack_options):
    widget.pack(**pack_options)


def _hide(widget):
    if hasattr(widget, "pack_forget"):
        widget.pack_forget()


def bind_analog_row(app, row, index, tag):
    runtime = getattr(app, "tag_runtime", None)
    runtime_value = runtime.get_value(tag.name) if runtime is not None else None
    try:
        initial_value = float(runtime_value) if runtime_value is not None else 0
    except (TypeError, ValueError):
        initial_value = 0
    row["current_tag_index"] = index
    row["tag"] = tag
    row["interactive"] = bool(tag.enabled_sim)
    row["address_label"].configure(text=tag.address)
    row["protocol_address_label"].configure(text=tag.address)
    _replace_entry(row["name_entry"], tag.name)
    row["value_label"].configure(text=f"{initial_value:g} RAW")
    row["live"].configure(text=f"{initial_value:g}")
    row["slider"].configure(from_=0, to=27648, command=lambda value, idx=index: on_slider_changed(app, idx, value))
    row["slider"].set(initial_value)
    row["start_button"].configure(command=lambda idx=index: on_profile_start(app, idx))
    row["stop_button"].configure(command=lambda idx=index: on_profile_stop(app, idx))
    settings = getattr(app, "_analog_profile_cache", {}).get(tag.name, {})
    row["profile_mode"].set(settings.get("mode", "Manual"))
    _replace_entry(row["min_entry"], settings.get("min", "0"))
    _replace_entry(row["max_entry"], settings.get("max", "27648"))
    _replace_entry(row["step_entry"], settings.get("step", "500"))
    _replace_entry(row["interval_entry"], settings.get("interval_ms", "500"))
    row["profile_status"].configure(text="MANUAL", text_color="gray")
    if tag.enabled_sim:
        row["name_entry"].configure(state="normal")
        _hide(row["readonly_label"])
        _show(row["profile_status"], side="left", padx=8)
        _show(row["slider"], padx=20, pady=12)
        _show(row["profile_frame"], fill="x", padx=10, pady=8)
    else:
        row["name_entry"].configure(state="disabled")
        _hide(row["profile_status"])
        _hide(row["slider"])
        _hide(row["profile_frame"])
        _show(row["readonly_label"], side="left", padx=8)
    app.analog_profile_directions[index] = 1


def create_analog_row(app, index, tag):
    """Compatibility helper used by row-level tests."""
    row = create_analog_row_widgets(app)
    # bind_analog_row normally runs before visible lists are populated.
    bind_analog_row(app, row, index, tag)
    row["frame"].pack(fill="x", padx=10, pady=10)
    app.analog_controls.append(row)
    app.analog_tags.append(tag)
    return row
