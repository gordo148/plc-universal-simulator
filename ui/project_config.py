import json
from tkinter import filedialog
from core.tag_model import Tag
from ui.header import SCHNEIDER_MODELS
from ui.tag_manager import refresh_tag_table


def save_project(app):
    config = {
        "tags": [tag.to_dict() for tag in getattr(app, "tags", [])],
        "brand": app.brand_menu.get(),
        "ip": app.ip_entry.get(),

        "digitals": [],
        "analogs": [],
        "alarms": [],

        "pid": {
            "sp": app.pid_sp_entry.get(),
            "pv_source": app.pid_pv_menu.get(),
            "out_address": app.pid_out_entry.get(),
            "kp": app.pid_kp_entry.get(),
            "ki": app.pid_ki_entry.get(),
            "kd": app.pid_kd_entry.get(),
            "out_min": app.pid_out_min_entry.get(),
            "out_max": app.pid_out_max_entry.get(),
            "interval_ms": app.pid_interval_entry.get()
        }
    }

    for item in app.digital_widgets:
        config["digitals"].append({
            "name": item["name_entry"].get(),
            "mode": item["mode_menu"].get(),
            "pulse_ms": item["pulse_entry"].get()
        })

    for item in app.analog_widgets:
        config["analogs"].append({
            "name": item["name_entry"].get(),
            "profile_mode": item["profile_mode"].get(),
            "min": item["min_entry"].get(),
            "max": item["max_entry"].get(),
            "step": item["step_entry"].get(),
            "interval_ms": item["interval_entry"].get()
        })

    if hasattr(app, "alarms"):
        for alarm in app.alarms:
            config["alarms"].append({
                "source": alarm["source"],
                "type": alarm["type"],
                "limit": alarm["limit"]
            })

    if app.brand_menu.get() == "Siemens":
        config["siemens"] = {
            "rack": app.rack_entry.get(),
            "slot": app.slot_entry.get(),
            "db": app.db_entry.get()
        }
    else:
        config["schneider"] = {
            "model": app.schneider_model_menu.get(),
            "port": app.port_entry.get(),
            "slave_id": app.slave_entry.get(),
            "coil_start": app.coil_start_entry.get(),
            "reg_start": app.reg_start_entry.get()
        }

    file_path = filedialog.asksaveasfilename(
        initialdir="configs",
        defaultextension=".json",
        filetypes=[("JSON files", "*.json")],
        initialfile="projeto_plc.json"
    )

    if not file_path:
        return

    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4, ensure_ascii=False)

    app.status_label.configure(text="● PROJETO GUARDADO", text_color="lime")


def load_project(app):
    file_path = filedialog.askopenfilename(
        initialdir="configs",
        filetypes=[("JSON files", "*.json")]
    )

    if not file_path:
        return

    with open(file_path, "r", encoding="utf-8") as file:
        config = json.load(file)

    app.tags = [
        Tag.from_dict(tag_data)
        for tag_data in config.get("tags", [])
        if isinstance(tag_data, dict)
    ]

    if hasattr(app, "tag_table"):
        refresh_tag_table(app)

    brand = config.get("brand", "Siemens")

    app.brand_menu.set(brand)
    app.update_brand(brand)

    app.ip_entry.delete(0, "end")
    app.ip_entry.insert(0, config.get("ip", "192.168.1.10"))

    if brand == "Siemens":
        siemens = config.get("siemens", {})

        app.rack_entry.delete(0, "end")
        app.rack_entry.insert(0, siemens.get("rack", "0"))

        app.slot_entry.delete(0, "end")
        app.slot_entry.insert(0, siemens.get("slot", "1"))

        app.db_entry.delete(0, "end")
        app.db_entry.insert(0, siemens.get("db", "100"))

    else:
        schneider = config.get("schneider", {})
        model = schneider.get("model", "M221")

        app.schneider_model_menu.set(model)

        app.port_entry.delete(0, "end")
        app.port_entry.insert(0, schneider.get("port", "502"))

        app.slave_entry.delete(0, "end")
        app.slave_entry.insert(0, schneider.get("slave_id", "1"))

        app.coil_start_entry.delete(0, "end")
        app.coil_start_entry.insert(0, schneider.get("coil_start", "0"))

        app.reg_start_entry.delete(0, "end")
        app.reg_start_entry.insert(0, schneider.get("reg_start", "0"))

        app.schneider_info.configure(text=SCHNEIDER_MODELS[model]["description"])

    app.generate_signals()

    digitals = config.get("digitals", [])

    for i, digital in enumerate(digitals):
        if i < len(app.digital_widgets):
            item = app.digital_widgets[i]

            item["name_entry"].delete(0, "end")
            item["name_entry"].insert(0, digital.get("name", f"DI_{i + 1:02d}"))

            item["mode_menu"].set(digital.get("mode", "Toggle"))

            item["pulse_entry"].delete(0, "end")
            item["pulse_entry"].insert(0, digital.get("pulse_ms", "500"))

            app.update_digital_name(i)

    analogs = config.get("analogs", [])

    for i, analog in enumerate(analogs):
        if i < len(app.analog_widgets):
            item = app.analog_widgets[i]

            item["name_entry"].delete(0, "end")
            item["name_entry"].insert(0, analog.get("name", f"AI_{i + 1:02d}"))

            item["profile_mode"].set(analog.get("profile_mode", "Manual"))

            item["min_entry"].delete(0, "end")
            item["min_entry"].insert(0, analog.get("min", "0"))

            item["max_entry"].delete(0, "end")
            item["max_entry"].insert(0, analog.get("max", "27648"))

            item["step_entry"].delete(0, "end")
            item["step_entry"].insert(0, analog.get("step", "500"))

            item["interval_entry"].delete(0, "end")
            item["interval_entry"].insert(0, analog.get("interval_ms", "500"))

    pid = config.get("pid", {})

    app.pid_sp_entry.delete(0, "end")
    app.pid_sp_entry.insert(0, pid.get("sp", "10000"))

    app.pid_out_entry.delete(0, "end")
    app.pid_out_entry.insert(0, pid.get("out_address", "20"))

    app.pid_kp_entry.delete(0, "end")
    app.pid_kp_entry.insert(0, pid.get("kp", "1.0"))

    app.pid_ki_entry.delete(0, "end")
    app.pid_ki_entry.insert(0, pid.get("ki", "0.0"))

    app.pid_kd_entry.delete(0, "end")
    app.pid_kd_entry.insert(0, pid.get("kd", "0.0"))

    app.pid_out_min_entry.delete(0, "end")
    app.pid_out_min_entry.insert(0, pid.get("out_min", "0"))

    app.pid_out_max_entry.delete(0, "end")
    app.pid_out_max_entry.insert(0, pid.get("out_max", "27648"))

    app.pid_interval_entry.delete(0, "end")
    app.pid_interval_entry.insert(0, pid.get("interval_ms", "500"))

    pv_source = pid.get("pv_source", "AI_01")

    try:
        app.pid_pv_menu.set(pv_source)
    except Exception:
        pass

    reload_alarms(app, config.get("alarms", []))

    app.status_label.configure(text="● PROJETO CARREGADO", text_color="lime")


def reload_alarms(app, alarms):
    if not hasattr(app, "alarms"):
        return

    from ui.alarm_tab import create_alarm_row, update_alarm_status
    from ui.tag_manager import get_alarm_tags

    for row in app.alarm_rows:
        try:
            row["state"].master.destroy()
        except Exception:
            pass

    app.alarms.clear()
    app.alarm_rows.clear()

    enabled_sources = [tag.name for tag in get_alarm_tags(app)]

    for alarm_config in alarms:
        alarm = {
            "source": alarm_config.get(
                "source",
                enabled_sources[0] if enabled_sources else ""
            ),
            "type": alarm_config.get("type", "HIGH"),
            "limit": int(alarm_config.get("limit", 20000)),
            "active": False,
            "ack": False,
            "last_value": 0,
            "timestamp": "-"
        }

        app.alarms.append(alarm)
        create_alarm_row(app, alarm)

    update_alarm_status(app)
