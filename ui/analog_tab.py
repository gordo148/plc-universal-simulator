import logging

import customtkinter as ctk
from ui.analog_profiles import start_profile, stop_profile


LOGGER = logging.getLogger(__name__)
ANALOG_PAGE_SIZE = 50
ANALOG_BATCH_SIZE = 10


def create_analog_tab(app):
    controls = ctk.CTkFrame(app.tab_analog)
    controls.pack(fill="x", padx=10, pady=(10, 0))
    ctk.CTkLabel(controls, text="Search").pack(side="left", padx=5)
    app.analog_search_entry = ctk.CTkEntry(controls, width=260)
    app.analog_search_entry.pack(side="left", padx=5)
    app.analog_search_entry.bind("<KeyRelease>", lambda _event: refresh_analog_tab(app, reset_page=True))
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
    app._analog_after_jobs = set()
    app._analog_rebuilding = False


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


def refresh_analog_tab(app, reset_page=False):
    from ui.tag_manager import get_input_analog_tags

    cancel_analog_refresh(app)
    if reset_page:
        app.analog_page = 0
    query = app.analog_search_entry.get().strip().casefold()
    tags = [
        tag for tag in get_input_analog_tags(app)
        if not query or query in tag.name.casefold() or query in tag.address.casefold()
    ]
    page_count = max(1, (len(tags) + ANALOG_PAGE_SIZE - 1) // ANALOG_PAGE_SIZE)
    app.analog_page = min(getattr(app, "analog_page", 0), page_count - 1)
    start = app.analog_page * ANALOG_PAGE_SIZE
    page_tags = tags[start:start + ANALOG_PAGE_SIZE]
    app._analog_rebuilding = True
    LOGGER.info("Analog lazy refresh start total=%d page=%d", len(tags), app.analog_page + 1)
    begin_analog_refresh(app, page_tags)
    app.analog_loading_label.configure(text=f"Loading analog signals 0/{len(page_tags)}")

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
        app._analog_after_jobs.add(job)

    def render_batch(offset):
        end = min(offset + ANALOG_BATCH_SIZE, len(page_tags))
        LOGGER.info("Analog lazy batch start range=%d:%d", offset, end)
        for local_index in range(offset, end):
            create_analog_row(app, local_index, page_tags[local_index])
        LOGGER.info("Analog lazy batch end rendered=%d total=%d", end, len(page_tags))
        app.analog_loading_label.configure(
            text=f"Loading analog signals {end}/{len(page_tags)}"
        )
        if end < len(page_tags):
            schedule(lambda: render_batch(end))
            return
        finish_analog_refresh(app)
        app._analog_rebuilding = False
        getattr(app, "_dirty_tabs", set()).discard("Entradas Analógicas")
        pending_profiles = getattr(app, "_pending_analog_profiles", None)
        if pending_profiles is not None:
            del app._pending_analog_profiles
            from ui.project_config import _restore_analog_profiles
            _restore_analog_profiles(app, pending_profiles)
        app.analog_loading_label.configure(
            text=f"Showing {start + 1 if page_tags else 0}-{start + len(page_tags)} of {len(tags)}"
        )
        app.analog_previous_button.configure(state="normal" if app.analog_page else "disabled")
        app.analog_next_button.configure(state="normal" if app.analog_page + 1 < page_count else "disabled")
        LOGGER.info("Analog lazy refresh complete rendered=%d", len(page_tags))

    schedule(lambda: render_batch(0))


def begin_analog_refresh(app, tags):
    """Clear analog controls without processing Tk events or touching the PLC."""
    LOGGER.info("Analog refresh started")
    for widget in app.analog_scroll.winfo_children():
        widget.destroy()
    app.analog_controls.clear()
    app.analog_tags.clear()
    app.analog_profile_running.clear()
    app.analog_profile_directions.clear()
    LOGGER.info("Analog refresh old widgets destroyed")
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


def create_analog_row(app, index, tag):
    LOGGER.info(
        "Analog widget creation started index=%d tag=%s type=%s",
        index, tag.name, tag.data_type,
    )
    runtime_value = None
    runtime_cache = getattr(app, "tag_runtime", None)
    if runtime_cache is not None:
        runtime_value = runtime_cache.get_value(tag.name)
    try:
        initial_value = float(runtime_value) if runtime_value is not None else 0
    except (TypeError, ValueError):
        initial_value = 0

    card = ctk.CTkFrame(app.analog_scroll, corner_radius=15)
    card.pack(fill="x", padx=10, pady=10)

    top = ctk.CTkFrame(card)
    top.pack(fill="x", padx=10, pady=8)

    visible = tag.address
    protocol_address = tag.address
    name = tag.name

    ctk.CTkLabel(top, text=visible, width=100, font=("Arial", 14, "bold")).pack(side="left", padx=8)
    ctk.CTkLabel(top, text=protocol_address, width=120, text_color="gray").pack(side="left", padx=8)

    if tag.enabled_sim:
        name_widget = ctk.CTkEntry(top, width=250)
        name_widget.insert(0, name)
    else:
        name_widget = ctk.CTkLabel(top, text=name, width=250, anchor="w")
    name_widget.pack(side="left", padx=8)

    value_label = ctk.CTkLabel(top, text=f"{initial_value:g} RAW", width=110, font=("Arial", 18, "bold"), text_color="cyan")
    value_label.pack(side="left", padx=8)

    live = ctk.CTkLabel(top, text=f"{initial_value:g}", width=80, font=("Arial", 18, "bold"))
    live.pack(side="left", padx=8)

    if not tag.enabled_sim:
        ctk.CTkLabel(
            top,
            text="PLC READ-ONLY",
            width=130,
            text_color="gray",
        ).pack(side="left", padx=8)
        app.analog_controls.append({
            "interactive": False,
            "name_entry": name_widget,
            "value_label": value_label,
            "live": live,
        })
        app.analog_tags.append(tag)
        LOGGER.info("Analog read-only row created index=%d tag=%s", index, tag.name)
        LOGGER.info("Analog widget creation completed index=%d tag=%s", index, tag.name)
        return

    profile_status = ctk.CTkLabel(top, text="MANUAL", width=100, text_color="gray")
    profile_status.pack(side="left", padx=8)

    slider = ctk.CTkSlider(
        card,
        from_=0,
        to=27648,
        width=750,
        command=lambda value, idx=index: on_slider_changed(app, idx, value)
    )
    # CTkSlider.set only changes local widget state. It does not read or write PLC.
    slider.set(initial_value)
    slider.pack(padx=20, pady=12)

    profile = ctk.CTkFrame(card)
    profile.pack(fill="x", padx=10, pady=8)

    ctk.CTkLabel(profile, text="Modo").pack(side="left", padx=5)

    profile_mode = ctk.CTkOptionMenu(
        profile,
        values=["Manual", "Ramp", "Random", "Step"],
        width=100
    )
    profile_mode.set("Manual")
    profile_mode.pack(side="left", padx=5)

    ctk.CTkLabel(profile, text="Min").pack(side="left", padx=5)
    min_entry = ctk.CTkEntry(profile, width=80)
    min_entry.insert(0, "0")
    min_entry.pack(side="left", padx=5)

    ctk.CTkLabel(profile, text="Max").pack(side="left", padx=5)
    max_entry = ctk.CTkEntry(profile, width=80)
    max_entry.insert(0, "27648")
    max_entry.pack(side="left", padx=5)

    ctk.CTkLabel(profile, text="Step").pack(side="left", padx=5)
    step_entry = ctk.CTkEntry(profile, width=80)
    step_entry.insert(0, "500")
    step_entry.pack(side="left", padx=5)

    ctk.CTkLabel(profile, text="Intervalo ms").pack(side="left", padx=5)
    interval_entry = ctk.CTkEntry(profile, width=90)
    interval_entry.insert(0, "500")
    interval_entry.pack(side="left", padx=5)

    ctk.CTkButton(
        profile,
        text="Start",
        width=90,
        command=lambda idx=index: on_profile_start(app, idx)
    ).pack(side="left", padx=8)

    ctk.CTkButton(
        profile,
        text="Stop",
        width=90,
        command=lambda idx=index: on_profile_stop(app, idx)
    ).pack(side="left", padx=8)

    app.analog_controls.append({
        "interactive": True,
        "name_entry": name_widget,
        "slider": slider,
        "value_label": value_label,
        "live": live,
        "profile_mode": profile_mode,
        "profile_status": profile_status,
        "min_entry": min_entry,
        "max_entry": max_entry,
        "step_entry": step_entry,
        "interval_entry": interval_entry,
    })
    app.analog_tags.append(tag)
    app.analog_profile_directions[index] = 1
    LOGGER.info("Analog callbacks registered index=%d tag=%s", index, tag.name)
    LOGGER.info("Analog widget creation completed index=%d tag=%s", index, tag.name)
