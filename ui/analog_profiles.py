import random


def start_profile(app, index):
    item = app.analog_widgets[index]

    mode = item["profile_mode"].get()

    if mode == "Manual":
        item["profile_status"].configure(text="MANUAL", text_color="gray")
        return

    app.analog_profile_running[index] = True
    item["profile_status"].configure(text=f"{mode} ON", text_color="lime")

    run_profile(app, index)


def stop_profile(app, index):
    app.analog_profile_running[index] = False

    item = app.analog_widgets[index]
    item["profile_status"].configure(text="STOP", text_color="gray")


def run_profile(app, index):
    if not app.analog_profile_running.get(index, False):
        return

    item = app.analog_widgets[index]

    try:
        mode = item["profile_mode"].get()
        min_value = int(item["min_entry"].get())
        max_value = int(item["max_entry"].get())
        step = int(item["step_entry"].get())
        interval_ms = int(item["interval_entry"].get())
    except ValueError:
        stop_profile(app, index)
        item["profile_status"].configure(text="ERRO", text_color="orange")
        return

    if interval_ms < 100:
        interval_ms = 100

    if step <= 0:
        step = 1

    if min_value > max_value:
        stop_profile(app, index)
        item["profile_status"].configure(text="ERRO", text_color="orange")
        return

    current_value = int(
        app.tag_runtime.get_value(item["tag"].name, 0)
    )

    if mode == "Ramp":
        direction = item["direction"]
        next_value = current_value + step * direction

        if next_value >= max_value:
            next_value = max_value
            item["direction"] = -1

        if next_value <= min_value:
            next_value = min_value
            item["direction"] = 1

    elif mode == "Random":
        next_value = random.randint(min_value, max_value)

    elif mode == "Step":
        if current_value <= min_value:
            next_value = max_value
        else:
            next_value = min_value

    else:
        return

    result = app.write_analog_by_index(index, next_value)

    if result is None:
        stop_profile(app, index)
        error_text = "ERRO PLC" if app.is_online() else "ERRO"
        item["profile_status"].configure(text=error_text, text_color="orange")
        return

    app.app.after(interval_ms, lambda: run_profile(app, index))
