import customtkinter as ctk
from ui.analog_profiles import start_profile, stop_profile


def create_analog_row(app, index, tag):
    card = ctk.CTkFrame(app.analog_scroll, corner_radius=15)
    card.pack(fill="x", padx=10, pady=10)

    top = ctk.CTkFrame(card)
    top.pack(fill="x", padx=10, pady=8)

    visible = tag.address
    protocol_address = tag.address
    name = tag.name

    ctk.CTkLabel(top, text=visible, width=100, font=("Arial", 14, "bold")).pack(side="left", padx=8)
    ctk.CTkLabel(top, text=protocol_address, width=120, text_color="gray").pack(side="left", padx=8)

    name_entry = ctk.CTkEntry(top, width=250)
    name_entry.insert(0, name)
    name_entry.pack(side="left", padx=8)

    value_label = ctk.CTkLabel(top, text="0 RAW", width=110, font=("Arial", 18, "bold"), text_color="cyan")
    value_label.pack(side="left", padx=8)

    live = ctk.CTkLabel(top, text="0", width=80, font=("Arial", 18, "bold"))
    live.pack(side="left", padx=8)

    profile_status = ctk.CTkLabel(top, text="MANUAL", width=100, text_color="gray")
    profile_status.pack(side="left", padx=8)

    slider = ctk.CTkSlider(
        card,
        from_=0,
        to=27648,
        width=750,
        command=lambda value, idx=index: app.update_analog(idx, value)
    )
    slider.set(0)
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
        command=lambda idx=index: start_profile(app, idx)
    ).pack(side="left", padx=8)

    ctk.CTkButton(
        profile,
        text="Stop",
        width=90,
        command=lambda idx=index: stop_profile(app, idx)
    ).pack(side="left", padx=8)

    app.analog_controls.append({
        "name_entry": name_entry,
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
