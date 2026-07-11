import customtkinter as ctk
import logging
import time
from tkinter import TclError
from tkinter import ttk

from ui.scrollable_frame import widget_exists


LOGGER = logging.getLogger(__name__)


DIGITAL_BATCH_SIZE = 25
PAGE_SIZES = (25, 50, 100)


def page_slice(items, page, page_size):
    page_size = max(1, int(page_size))
    page_count = max(1, (len(items) + page_size - 1) // page_size)
    page = min(max(0, int(page)), page_count - 1)
    start = page * page_size
    return page, page_count, start, items[start:start + page_size]


def create_digital_tab_structure(app):
    """Create persistent Digital controls exactly once."""
    if getattr(app, "_digital_structure_initialized", False):
        return
    started = time.perf_counter()
    controls = ctk.CTkFrame(app.tab_digital)
    controls.pack(fill="x", padx=10, pady=(10, 0))
    ctk.CTkLabel(controls, text="Tags per page").pack(side="left", padx=5)
    app.digital_page_size_menu = ctk.CTkOptionMenu(
        controls, values=[str(size) for size in PAGE_SIZES], width=75,
        command=lambda _value: refresh_digital_tab(app),
    )
    app.digital_page_size_menu.set("50")
    app.digital_page_size_menu.pack(side="left", padx=5)
    app.digital_previous_button = ctk.CTkButton(
        controls, text="Previous", width=85,
        command=lambda: change_digital_page(app, -1),
    )
    app.digital_previous_button.pack(side="left", padx=5)
    app.digital_next_button = ctk.CTkButton(
        controls, text="Next", width=85,
        command=lambda: change_digital_page(app, 1),
    )
    app.digital_next_button.pack(side="left", padx=5)
    app.digital_loading_label = ctk.CTkLabel(controls, text="Digital signals not loaded")
    app.digital_loading_label.pack(side="left", padx=15)
    app.digital_page = 0
    app.digital_row_pool = []
    app._digital_after_jobs = set()
    app._digital_rebuilding = False
    app._digital_structure_initialized = True
    _create_digital_master_detail(app)
    LOGGER.info(
        "Digital tab structure created: widgets_created=16 callbacks_registered=4 structure_time_ms=%.3f",
        (time.perf_counter() - started) * 1000,
    )


create_digital_tab = create_digital_tab_structure


def _create_digital_master_detail(app):
    body = ctk.CTkFrame(app.tab_digital)
    body.pack(fill="both", expand=True, padx=10, pady=10)
    table_frame = ctk.CTkFrame(body)
    table_frame.pack(fill="both", expand=True)
    columns = ("status", "address", "name", "mode", "value")
    table = ttk.Treeview(table_frame, columns=columns, show="headings", height=18)
    for column, title, width in (
        ("status", "Status", 70), ("address", "Address", 120),
        ("name", "Name", 260), ("mode", "Mode", 90), ("value", "Value", 80),
    ):
        table.heading(column, text=title)
        table.column(column, width=width, anchor="center" if column != "name" else "w")
    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
    table.configure(yscrollcommand=scrollbar.set)
    table.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    editor = ctk.CTkFrame(body)
    editor.pack(fill="x", pady=(8, 0))
    app.digital_editor_title = ctk.CTkLabel(editor, text="Select a digital tag")
    app.digital_editor_title.grid(row=0, column=0, padx=8, pady=8)
    app.digital_editor_mode = ctk.CTkOptionMenu(editor, values=["Toggle", "Pulse"], width=100)
    app.digital_editor_mode.grid(row=0, column=1, padx=8)
    app.digital_editor_pulse = ctk.CTkEntry(editor, width=90)
    app.digital_editor_pulse.insert(0, "500")
    app.digital_editor_pulse.grid(row=0, column=2, padx=8)
    app.digital_editor_button = ctk.CTkButton(editor, text="OFF", width=140, command=lambda: _digital_editor_action(app))
    app.digital_editor_button.grid(row=0, column=3, padx=8)
    app.digital_editor_value = ctk.CTkLabel(editor, text="0", width=60)
    app.digital_editor_value.grid(row=0, column=4, padx=8)
    table.bind("<<TreeviewSelect>>", lambda _event: _bind_selected_digital(app))
    app.digital_table = table
    app.digital_table_scrollbar = scrollbar
    app.digital_editor = editor
    app.digital_scroll = editor  # compatibility parent; normal refresh creates no rows here
    app._digital_table_tags = []
    app._digital_selected_tag_name = None


def _digital_editor_action(app):
    if app.digital_tags:
        app.digital_action(0)


def _bind_selected_digital(app):
    selection = app.digital_table.selection()
    if not selection:
        return
    position = app.digital_table.index(selection[0])
    if position >= len(app._digital_table_tags):
        return
    tag = app._digital_table_tags[position]
    app._digital_selected_tag_name = tag.name
    settings = getattr(app, "_digital_settings_cache", {}).get(tag.name, {})
    app.digital_editor_title.configure(text=f"{tag.name} · {tag.address}")
    app.digital_editor_mode.set(settings.get("mode", "Toggle"))
    _replace_entry(app.digital_editor_pulse, settings.get("pulse_ms", "500"))
    state = bool(app.tag_runtime.get_value(tag.name, False))
    app.digital_editor_button.configure(text=f"{tag.name} {'ON' if state else 'OFF'}")
    app.digital_editor_value.configure(text="1" if state else "0")
    app.digital_tags[:] = [tag]
    app.digital_controls[:] = [{
        "mode_menu": app.digital_editor_mode, "pulse_entry": app.digital_editor_pulse,
        "button": app.digital_editor_button, "led": app.digital_editor_value,
        "live": app.digital_editor_value, "name_entry": app.digital_editor_title,
    }]
    app.digital_states.clear()
    app.digital_states[0] = state


def cancel_digital_refresh(app):
    for job in tuple(getattr(app, "_digital_after_jobs", set())):
        try:
            app.cancel_job(job)
        except TclError:
            pass
    getattr(app, "_digital_after_jobs", set()).clear()
    app._digital_rebuilding = False


def change_digital_page(app, offset):
    app.digital_page = max(0, getattr(app, "digital_page", 0) + offset)
    refresh_digital_tab(app)


def _remember_visible_settings(app):
    cache = getattr(app, "_digital_settings_cache", {})
    for index, item in enumerate(app.digital_controls):
        if index < len(app.digital_tags):
            tag_name = app.digital_tags[index].name
            cache[tag_name] = {
                "tag": tag_name,
                "mode": item["mode_menu"].get(),
                "pulse_ms": item["pulse_entry"].get(),
            }
    app._digital_settings_cache = cache


def refresh_digital_visible_rows(app, reset_page=False):
    """Rebind the persistent row pool to the requested page."""
    refresh_started = time.perf_counter()
    from ui.tag_manager import get_input_bool_tags

    cancel_digital_refresh(app)
    _remember_visible_settings(app)
    if reset_page:
        app.digital_page = 0
    tags = get_input_bool_tags(app)
    size = int(app.digital_page_size_menu.get())
    page, count, start, visible = page_slice(tags, app.digital_page, size)
    app.digital_page = page
    app._digital_rebuilding = True
    if hasattr(app, "digital_table"):
        _refresh_digital_table(app, tags, page, count, start, visible, refresh_started)
        return
    app.digital_loading_label.configure(text=f"Generating signals: 0 / {len(visible)}")

    pool = getattr(app, "digital_row_pool", None)
    if pool is None:
        pool = app.digital_row_pool = []

    def finish():
        if getattr(app, "is_closing", False) or not widget_exists(app.digital_loading_label):
            return
        app.digital_controls[:] = []
        app.digital_tags[:] = []
        app.digital_states.clear()
        for index, row in enumerate(pool):
            if index < len(visible):
                bind_digital_row(app, row, index, visible[index])
                row["frame"].pack(fill="x", padx=10, pady=6)
                app.digital_controls.append(row)
                app.digital_tags.append(visible[index])
            else:
                row["current_tag_index"] = None
                row["tag"] = None
                row["frame"].pack_forget()
        app._digital_rebuilding = False
        getattr(app, "_dirty_tabs", set()).discard("Entradas Digitais")
        app.digital_loading_label.configure(
            text=f"Page {page + 1} of {count} · "
                 f"{start + 1 if visible else 0}-{start + len(visible)} of {len(tags)}"
        )
        app.digital_previous_button.configure(state="normal" if page else "disabled")
        app.digital_next_button.configure(state="normal" if page + 1 < count else "disabled")
        pending = getattr(app, "_pending_digital_settings", None)
        if pending is not None:
            del app._pending_digital_settings
            from ui.project_config import _restore_digital_settings
            _restore_digital_settings(app, pending)
        _set_refresh_button(app, "normal")
        LOGGER.info(
            "Digital page refreshed: page=%d visible=%d total=%d",
            page + 1, len(visible), len(tags),
        )

    def grow_pool():
        job = None
        def grow_batch():
            app._digital_after_jobs.discard(job)
            if getattr(app, "is_closing", False) or not widget_exists(app.digital_loading_label):
                return
            old_size = len(pool)
            target = min(len(visible), len(pool) + DIGITAL_BATCH_SIZE)
            while len(pool) < target:
                pool.append(create_digital_row_widgets(app))
            if len(pool) != old_size:
                LOGGER.info("Digital row pool expanded: old=%d new=%d", old_size, len(pool))
            app.digital_loading_label.configure(
                text=f"Generating signals: {min(len(pool), len(visible))} / {len(visible)}"
            )
            if len(pool) < len(visible):
                grow_pool()
            else:
                finish()
        job = app.schedule_job(1, grow_batch)
        if job is not None:
            app._digital_after_jobs.add(job)

    if len(pool) < len(visible):
        grow_pool()
    else:
        finish()


refresh_digital_tab = refresh_digital_visible_rows


def _refresh_digital_table(app, tags, page, count, start, visible, refresh_started):
    selected = getattr(app, "_digital_selected_tag_name", None)
    table = app.digital_table
    table.delete(*table.get_children())
    app._digital_table_tags = list(visible)
    selected_item = None
    for tag in visible:
        state = bool(app.tag_runtime.get_value(tag.name, False))
        settings = getattr(app, "_digital_settings_cache", {}).get(tag.name, {})
        item = table.insert("", "end", values=(
            "ON" if state else "OFF", tag.address, tag.name,
            settings.get("mode", "Toggle"), "1" if state else "0",
        ))
        if tag.name == selected:
            selected_item = item
    app.digital_page = page
    app._digital_rebuilding = False
    app._dirty_tabs.discard("Entradas Digitais")
    app.digital_loading_label.configure(text=f"Page {page + 1} of {count} · {start + 1 if visible else 0}-{start + len(visible)} of {len(tags)}")
    app.digital_previous_button.configure(state="normal" if page else "disabled")
    app.digital_next_button.configure(state="normal" if page + 1 < count else "disabled")
    if selected_item is None and table.get_children():
        selected_item = table.get_children()[0]
    if selected_item is not None:
        table.selection_set(selected_item)
        _bind_selected_digital(app)
    LOGGER.info(
        "Digital tab generation: tags_total=%d visible_rows=%d widgets_created=0 callbacks_registered=0 row_creation_time_ms=0 layout_time_ms=%.3f total_time_ms=%.3f",
        len(tags), len(visible), 0.0, (time.perf_counter() - refresh_started) * 1000,
    )


def update_digital_table_values(app):
    table = getattr(app, "digital_table", None)
    if table is None or not widget_exists(table):
        return
    for item, tag in zip(table.get_children(), app._digital_table_tags):
        state = bool(app.tag_runtime.get_value(tag.name, False))
        values = list(table.item(item, "values"))
        values[0], values[4] = ("ON" if state else "OFF"), ("1" if state else "0")
        table.item(item, values=values)
    _bind_selected_digital(app)


def _set_refresh_button(app, state):
    button = getattr(app, "tag_update_signals_button", None)
    if button is not None:
        button.configure(state=state)


def _replace_entry(entry, value):
    entry.delete(0, "end")
    entry.insert(0, value)


def create_digital_row_widgets(app):
    frame = ctk.CTkFrame(app.digital_scroll, corner_radius=15)
    led = ctk.CTkLabel(frame, text="●", text_color="gray", font=("Arial", 26))
    led.grid(row=0, column=0, padx=10, pady=8)
    address = ctk.CTkLabel(frame, text="", width=120, font=("Arial", 14, "bold"))
    address.grid(row=0, column=1, padx=10)
    protocol_address = ctk.CTkLabel(frame, text="", width=120, text_color="gray")
    protocol_address.grid(row=0, column=2, padx=10)
    name_entry = ctk.CTkEntry(frame, width=230)
    name_entry.grid(row=0, column=3, padx=10)
    mode_menu = ctk.CTkOptionMenu(frame, values=["Toggle", "Pulse"], width=100)
    mode_menu.grid(row=0, column=4, padx=8)
    pulse_entry = ctk.CTkEntry(frame, width=80)
    pulse_entry.grid(row=0, column=5, padx=8)
    ctk.CTkLabel(frame, text="ms", width=30).grid(row=0, column=6, padx=2)
    button = ctk.CTkButton(frame, text="OFF", width=160)
    button.grid(row=0, column=7, padx=10)
    live = ctk.CTkLabel(frame, text="0", width=40, font=("Arial", 16, "bold"))
    live.grid(row=0, column=8, padx=10)
    return {
        "frame": frame, "led": led, "address_label": address,
        "protocol_address_label": protocol_address, "name_entry": name_entry,
        "mode_menu": mode_menu, "pulse_entry": pulse_entry, "button": button,
        "live": live, "current_tag_index": None, "tag": None,
    }


def bind_digital_row(app, row, index, tag):
    """Assign a tag and replace every tag-specific callback on a pooled row."""
    row["current_tag_index"] = index
    row["tag"] = tag
    row["address_label"].configure(text=tag.address)
    row["protocol_address_label"].configure(text=tag.address)
    _replace_entry(row["name_entry"], tag.name)
    settings = getattr(app, "_digital_settings_cache", {}).get(tag.name, {})
    row["mode_menu"].set(settings.get("mode", "Toggle"))
    _replace_entry(row["pulse_entry"], str(settings.get("pulse_ms", "500")))
    row["button"].configure(command=lambda idx=index: app.digital_action(idx))
    row["name_entry"].unbind("<KeyRelease>")
    row["name_entry"].bind(
        "<KeyRelease>", lambda _event, idx=index: app.update_digital_name(idx)
    )
    runtime = getattr(app, "tag_runtime", None)
    state = bool(runtime.get_value(tag.name, False)) if runtime else False
    app.digital_states[index] = state
    row["button"].configure(text=f"{tag.name} {'ON' if state else 'OFF'}")
    row["led"].configure(text="●", text_color="lime" if state else "gray")
    row["live"].configure(text="1" if state else "0")


def create_digital_row(app, index, tag):
    """Compatibility helper used by focused row-construction tests."""
    row = create_digital_row_widgets(app)
    bind_digital_row(app, row, index, tag)
    row["frame"].pack(fill="x", padx=10, pady=6)
    app.digital_controls.append(row)
    app.digital_tags.append(tag)
    return row
