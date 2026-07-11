import customtkinter as ctk
import logging
from tkinter import TclError

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


create_digital_tab = create_digital_tab_structure


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
