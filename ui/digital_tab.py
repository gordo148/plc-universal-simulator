import customtkinter as ctk
import logging
import time
from tkinter import Menu, TclError
from tkinter import ttk

from ui.scrollable_frame import widget_exists
from core.tag_runtime import RuntimeValueSource
from ui.table_utils import (
    PAGE_SIZES, ToolTip, clear_entry, copy_text, debounce, filter_tags,
    move_selection, page_tags, sort_tags,
)


LOGGER = logging.getLogger(__name__)


DIGITAL_BATCH_SIZE = 25
def page_slice(items, page, page_size):
    return page_tags(items, page, page_size)


def create_digital_tab_structure(app):
    """Create persistent Digital controls exactly once."""
    if getattr(app, "_digital_structure_initialized", False):
        return
    started = time.perf_counter()
    controls = ctk.CTkFrame(app.tab_digital)
    controls.pack(fill="x", padx=10, pady=(10, 0))
    ctk.CTkLabel(controls, text="Search").pack(side="left", padx=(5, 2))
    app.digital_search_entry = ctk.CTkEntry(controls, width=240, placeholder_text="Name, address or type")
    app.digital_search_entry.pack(side="left", padx=3)
    app.digital_search_clear = ctk.CTkButton(controls, text="×", width=30, command=lambda: clear_digital_search(app))
    app.digital_search_clear.pack(side="left", padx=(0, 8))
    app.digital_search_entry.bind("<KeyRelease>", lambda event: _digital_search_key(app, event))
    ctk.CTkLabel(controls, text="Tags per page").pack(side="left", padx=5)
    app.digital_page_size_menu = ctk.CTkOptionMenu(
        controls, values=list(PAGE_SIZES), width=75,
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
    app._digital_sort_column = "name"
    app._digital_sort_descending = False
    app._digital_last_values = {}
    app._digital_highlight_jobs = {}
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
    columns = ("status", "address", "name", "mode", "value", "difference")
    table = ttk.Treeview(table_frame, columns=columns, show="headings", height=18)
    for column, title, width in (
        ("status", "Status", 70), ("address", "Address", 120),
        ("name", "Name", 240), ("mode", "Mode", 90), ("value", "Value", 80),
        ("difference", "PLC / Sim", 120),
    ):
        table.heading(column, text=title, command=lambda col=column: sort_digital_table(app, col))
        table.column(column, width=width, anchor="center" if column != "name" else "w")
    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
    table.configure(yscrollcommand=scrollbar.set)
    table.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    editor = ctk.CTkFrame(body)
    editor.pack(fill="x", pady=(8, 0))
    app.digital_editor_title = ctk.CTkLabel(editor, text="Select a digital tag", font=("Arial", 14, "bold"))
    app.digital_editor_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 2))
    app.digital_editor_plc = ctk.CTkLabel(editor, text="PLC: —", width=100)
    app.digital_editor_plc.grid(row=1, column=0, padx=8, pady=6)
    app.digital_editor_sim = ctk.CTkLabel(editor, text="Simulated: —", width=120)
    app.digital_editor_sim.grid(row=1, column=1, padx=8)
    app.digital_editor_mode = ctk.CTkOptionMenu(editor, values=["Toggle", "Pulse"], width=100)
    app.digital_editor_mode.grid(row=1, column=2, padx=8)
    app.digital_editor_pulse = ctk.CTkEntry(editor, width=90)
    app.digital_editor_pulse.insert(0, "500")
    app.digital_editor_pulse.grid(row=1, column=3, padx=8)
    app.digital_editor_button = ctk.CTkButton(editor, text="Toggle", width=110, command=lambda: _digital_editor_action(app))
    app.digital_editor_button.grid(row=1, column=4, padx=8)
    app.digital_editor_write = ctk.CTkButton(editor, text="Write", width=90, command=lambda: _write_selected_digital(app))
    app.digital_editor_write.grid(row=1, column=5, padx=8)
    app.digital_editor_value = ctk.CTkLabel(editor, text="0", width=60)
    app.digital_editor_value.grid(row=1, column=6, padx=8)
    table.bind("<<TreeviewSelect>>", lambda _event: _bind_selected_digital(app))
    table.bind("<Double-1>", lambda _event: _digital_editor_action(app))
    table.bind("<Button-3>", lambda event: show_digital_context_menu(app, event))
    table.bind("<Key>", lambda event: handle_digital_key(app, event))
    app.digital_table = table
    app.digital_table_scrollbar = scrollbar
    app.digital_editor = editor
    app.digital_scroll = editor  # compatibility parent; normal refresh creates no rows here
    app._digital_table_tags = []
    app._digital_selected_tag_name = None
    for widget, text in ((app.digital_editor_button, "Toggle the selected signal or execute its pulse mode."), (app.digital_editor_write, "Write the current simulated value."), (app.digital_editor_mode, "Choose Toggle or timed Pulse mode."), (app.digital_editor_pulse, "Pulse duration in milliseconds."), (app.digital_editor_value, "Latest runtime value.")):
        ToolTip(widget, text)


def _digital_search_key(app, event):
    if getattr(event, "keysym", "") == "Escape":
        clear_digital_search(app)
        return
    debounce(app, "digital_search", 150, lambda: refresh_digital_tab(app, reset_page=True))


def clear_digital_search(app):
    clear_entry(app.digital_search_entry)
    refresh_digital_tab(app, reset_page=True)


def sort_digital_table(app, column):
    if app._digital_sort_column == column:
        app._digital_sort_descending = not app._digital_sort_descending
    else:
        app._digital_sort_column, app._digital_sort_descending = column, False
    app._digital_preserve_selection = getattr(app, "_digital_selected_tag_name", None)
    refresh_digital_tab(app, reset_page=True)


def _selected_digital_tag(app):
    selection = app.digital_table.selection()
    if not selection: return None
    index = app.digital_table.index(selection[0])
    return app._digital_table_tags[index] if index < len(app._digital_table_tags) else None


def _write_selected_digital(app):
    if app.digital_tags:
        value = getattr(app, "_simulated_values", {}).get(app.digital_tags[0].name, app.digital_states.get(0, False))
        app.write_digital_state(0, bool(value))


def handle_digital_key(app, event):
    key = event.keysym
    if key in ("Up", "Down", "Prior", "Next", "Home", "End"):
        move_selection(app.digital_table, key); _bind_selected_digital(app); return "break"
    if key in ("space", "Return"):
        _digital_editor_action(app); return "break"
    if key == "Delete":
        app.write_digital_state(0, False) if app.digital_tags else None; return "break"


def show_digital_context_menu(app, event):
    row = app.digital_table.identify_row(event.y)
    if row: app.digital_table.selection_set(row); _bind_selected_digital(app)
    tag = _selected_digital_tag(app)
    if tag is None: return
    menu = Menu(app.digital_table, tearoff=False)
    menu.add_command(label="Toggle", command=lambda: _digital_editor_action(app))
    menu.add_command(label="Force ON", command=lambda: app.write_digital_state(0, True))
    menu.add_command(label="Force OFF", command=lambda: app.write_digital_state(0, False))
    menu.add_separator()
    menu.add_command(label="Copy Address", command=lambda: copy_text(app.digital_table, tag.address))
    menu.add_command(label="Copy Name", command=lambda: copy_text(app.digital_table, tag.name))
    menu.add_command(label="Copy Full Tag", command=lambda: copy_text(app.digital_table, f"{tag.name}\t{tag.address}\t{tag.data_type}"))
    menu.tk_popup(event.x_root, event.y_root)


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
    selection_changed = getattr(app, "_digital_selected_tag_name", None) != tag.name or not app.digital_tags
    app._digital_selected_tag_name = tag.name
    settings = getattr(app, "_digital_settings_cache", {}).get(tag.name, {})
    app.digital_editor_title.configure(text=f"{tag.name} · {tag.address}")
    if selection_changed:
        app.digital_editor_mode.set(settings.get("mode", "Toggle"))
        _replace_entry(app.digital_editor_pulse, settings.get("pulse_ms", "500"))
    state = bool(app.tag_runtime.get_value(tag.name, False))
    app.digital_editor_button.configure(text=f"{tag.name} {'ON' if state else 'OFF'}")
    app.digital_editor_value.configure(text="1" if state else "0")
    plc = getattr(app, "_plc_values", {}).get(tag.name, "—")
    simulated = getattr(app, "_simulated_values", {}).get(tag.name, state)
    if hasattr(app, "digital_editor_plc"):
        app.digital_editor_plc.configure(text=f"PLC: {plc}")
    if hasattr(app, "digital_editor_sim"):
        app.digital_editor_sim.configure(text=f"Simulated: {simulated}")
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
    tags = filter_tags(get_input_bool_tags(app), app.digital_search_entry.get() if hasattr(app, "digital_search_entry") else "")
    runtime = getattr(app, "tag_runtime", None)
    values = {tag.name: runtime.get_value(tag.name) if runtime else None for tag in tags}
    if getattr(app, "_digital_sort_column", "name") == "difference":
        values = {tag.name: getattr(app, "_plc_values", {}).get(tag.name) != getattr(app, "_simulated_values", {}).get(tag.name) for tag in tags}
    tags = sort_tags(tags, getattr(app, "_digital_sort_column", "name"), getattr(app, "_digital_sort_descending", False), getattr(app, "_digital_settings_cache", {}), values)
    preserve = getattr(app, "_digital_preserve_selection", None)
    if preserve:
        names = [tag.name for tag in tags]
        if preserve in names and app.digital_page_size_menu.get() != "All":
            app.digital_page = names.index(preserve) // int(app.digital_page_size_menu.get())
        app._digital_preserve_selection = None
    page, count, start, visible = page_slice(tags, app.digital_page, app.digital_page_size_menu.get())
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
        plc = getattr(app, "_plc_values", {}).get(tag.name)
        simulated = getattr(app, "_simulated_values", {}).get(tag.name)
        different = plc is not None and simulated is not None and bool(plc) != bool(simulated)
        item = table.insert("", "end", values=(
            "🟢 ON" if state else "🔴 OFF", tag.address, tag.name,
            settings.get("mode", "Toggle"), "1" if state else "0", "⚠ differs" if different else "✓ identical",
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
    titles = {"status":"Status", "address":"Address", "name":"Name", "mode":"Mode", "value":"Value", "difference":"PLC / Sim"}
    if hasattr(table, "heading"):
        for column, title in titles.items():
            marker = " ▼" if getattr(app, "_digital_sort_descending", False) else " ▲"
            table.heading(column, text=title + (marker if column == getattr(app, "_digital_sort_column", "name") else ""), command=lambda col=column: sort_digital_table(app, col))
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
        runtime_item = app.tag_runtime.get(tag.name)
        if runtime_item and runtime_item.valid and runtime_item.source == RuntimeValueSource.PLC:
            app._plc_values[tag.name] = bool(runtime_item.value)
        values = list(table.item(item, "values"))
        previous = app._digital_last_values.get(tag.name)
        values[0], values[4] = ("🟢 ON" if state else "🔴 OFF"), ("1" if state else "0")
        plc = getattr(app, "_plc_values", {}).get(tag.name)
        simulated = getattr(app, "_simulated_values", {}).get(tag.name)
        values[5] = "⚠ differs" if plc is not None and simulated is not None and bool(plc) != bool(simulated) else "✓ identical"
        table.item(item, values=values)
        if previous is not None and previous != state and hasattr(table, "tag_configure"):
            table.tag_configure("changed", background="#145a78")
            table.item(item, tags=("changed",))
            old_job = app._digital_highlight_jobs.pop(tag.name, None)
            if old_job: app.cancel_job(old_job)
            app._digital_highlight_jobs[tag.name] = app.schedule_job(1000, lambda row=item, name=tag.name: _clear_digital_highlight(app, row, name))
        app._digital_last_values[tag.name] = state
    _bind_selected_digital(app)


def _clear_digital_highlight(app, item, tag_name):
    app._digital_highlight_jobs.pop(tag_name, None)
    if widget_exists(app.digital_table) and item in app.digital_table.get_children():
        app.digital_table.item(item, tags=())


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
