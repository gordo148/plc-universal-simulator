import copy
import json
import os
import tempfile
from tkinter import filedialog, messagebox

from core.tag_model import Tag
from ui.header import SCHNEIDER_MODELS, update_top_status_bar
from ui.tag_manager import (
    get_numeric_tags,
    get_pid_output_tags,
    get_tag_by_name,
    normalize_and_validate_tag_names,
    refresh_tag_table,
    update_tag_address_context,
)


PROJECT_EXTENSION = ".simproject"
PROJECT_FORMAT = "plc-universal-simulator-project"
PROJECT_VERSION = 1
SUPPORTED_BRANDS = (
    "Siemens",
    "Schneider",
    "Modbus TCP",
    "Rockwell",
    "Omron",
    "Simulator",
)


def new_project(app):
    if not _apply_project_data(app, _stage_project_data(_default_project_data())):
        return False

    app.project_path = None
    _update_project_title(app)
    from ui.dashboard_tab import clear_dashboard_events, update_dashboard
    clear_dashboard_events(app)
    update_dashboard(app, "Novo projeto criado")
    app.status_label.configure(text="● NOVO PROJETO", text_color="lime")
    return True


def save_project(app):
    file_path = getattr(app, "project_path", None)
    if not file_path:
        return save_project_as(app)
    return _write_project(app, file_path)


def save_project_as(app):
    file_path = filedialog.asksaveasfilename(
        initialdir="configs",
        defaultextension=PROJECT_EXTENSION,
        filetypes=[("Simulator projects", f"*{PROJECT_EXTENSION}")],
        initialfile=f"project{PROJECT_EXTENSION}",
    )
    if not file_path:
        return False

    return _write_project(app, _project_path(file_path))


def open_project(app):
    file_path = filedialog.askopenfilename(
        initialdir="configs",
        filetypes=[("Simulator projects", f"*{PROJECT_EXTENSION}")],
    )
    if not file_path:
        return False

    return open_project_path(app, file_path)


def open_project_path(app, file_path):
    """Open a project from a known path, including a recent-project entry."""

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            project = json.load(file)
        staged_project = _stage_project_data(project)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        messagebox.showerror("Erro ao abrir projeto", str(error))
        return False

    current_project = _stage_project_data(build_project_data(app))
    runtime_snapshot = app.tag_runtime.snapshot()
    current_path = getattr(app, "project_path", None)

    if not _apply_project_data(app, staged_project):
        _apply_project_data(app, current_project, show_error=False)
        app.tag_runtime.restore(runtime_snapshot, app.tags)
        app.project_path = current_path
        _update_project_title(app)
        if hasattr(app, "update_runtime_widgets"):
            app.update_runtime_widgets()
        return False

    app.project_path = file_path
    _update_project_title(app)
    app.status_label.configure(text="● PROJETO ABERTO", text_color="lime")
    return True


def build_project_data(app):
    brand = app.brand_menu.get()
    output_tag = get_tag_by_name(app, app.pid_out_menu.get())

    connection = {
        "brand": brand,
        "ip": "" if brand == "Simulator" else app.ip_entry.get(),
        "settings": {},
    }
    if brand == "Siemens":
        connection["settings"] = {
            "rack": app.rack_entry.get(),
            "slot": app.slot_entry.get(),
            "db_number": app.db_entry.get(),
        }
    elif brand == "Schneider":
        connection["settings"] = {
            "model": app.schneider_model_menu.get(),
            "port": app.port_entry.get(),
            "slave_id": app.slave_entry.get(),
            "coil_start": app.coil_start_entry.get(),
            "register_start": app.reg_start_entry.get(),
        }
    elif brand == "Modbus TCP":
        connection["settings"] = {
            "port": app.port_entry.get(),
            "slave_id": app.slave_entry.get(),
        }
    elif brand == "Omron":
        connection["settings"] = {
            "port": app.port_entry.get(),
            "destination_node": app.destination_node_entry.get(),
            "source_node": app.source_node_entry.get(),
        }

    digital_inputs = []
    for item in getattr(app, "digital_widgets", []):
        digital_inputs.append({
            "tag": item["tag"].name,
            "mode": item["mode_menu"].get(),
            "pulse_ms": item["pulse_entry"].get(),
        })

    analog_profiles = []
    for item in getattr(app, "analog_widgets", []):
        analog_profiles.append({
            "tag": item["tag"].name,
            "mode": item["profile_mode"].get(),
            "min": item["min_entry"].get(),
            "max": item["max_entry"].get(),
            "step": item["step_entry"].get(),
            "interval_ms": item["interval_entry"].get(),
        })

    alarms = [
        {
            "source": alarm["source"],
            "type": alarm["type"],
            "limit": alarm["limit"],
        }
        for alarm in getattr(app, "alarms", [])
    ]

    selected_curves = [
        name
        for name, variable in getattr(app, "trend_tag_vars", {}).items()
        if variable.get()
    ]
    trend_auto_scale = getattr(app, "trend_auto_scale", None)
    pending_trends = getattr(app, "_pending_trend_settings", {})
    if not selected_curves and not hasattr(app, "trend_tag_vars"):
        selected_curves = list(pending_trends.get("selected_curves", []))

    return {
        "format": PROJECT_FORMAT,
        "version": PROJECT_VERSION,
        "plc": connection,
        "tags": [
            tag.to_dict()
            for tag in getattr(app, "tags", [])
        ],
        "runtime_settings": {
            "digital_inputs": digital_inputs,
        },
        "alarms": alarms,
        "pid": {
            "sp": app.pid_sp_entry.get(),
            "sp_source": app.pid_sp_source_menu.get(),
            "pv_source": app.pid_pv_menu.get(),
            "out_source": app.pid_out_menu.get(),
            "out_address": output_tag.address if output_tag else "",
            "kp": app.pid_kp_entry.get(),
            "ki": app.pid_ki_entry.get(),
            "kd": app.pid_kd_entry.get(),
            "out_min": app.pid_out_min_entry.get(),
            "out_max": app.pid_out_max_entry.get(),
            "interval_ms": app.pid_interval_entry.get(),
        },
        "trends": {
            "enabled_tags": [
                tag.name for tag in getattr(app, "tags", [])
                if tag.enabled_trend
            ],
            "selected_curves": selected_curves,
            "auto_scale": (
                bool(trend_auto_scale.get())
                if trend_auto_scale is not None
                else bool(pending_trends.get("auto_scale", True))
            ),
        },
        "dashboard": {
            "enabled_tags": [
                tag.name for tag in getattr(app, "tags", [])
                if tag.enabled_dashboard
            ],
        },
        "analog_profiles": analog_profiles,
    }


def _write_project(app, file_path):
    temporary_path = None
    try:
        project = _stage_project_data(build_project_data(app))
        destination = os.path.abspath(file_path)
        directory = os.path.dirname(destination)
        os.makedirs(directory, exist_ok=True)

        descriptor, temporary_path = tempfile.mkstemp(
            prefix=f".{os.path.basename(destination)}.",
            suffix=".tmp",
            dir=directory,
            text=True,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(
                project,
                file,
                indent=4,
                ensure_ascii=False,
            )
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, destination)
        temporary_path = None
    except Exception as error:
        if temporary_path and os.path.exists(temporary_path):
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
        messagebox.showerror("Erro ao guardar projeto", str(error))
        return False

    app.project_path = file_path
    _update_project_title(app)
    app.status_label.configure(text="● PROJETO GUARDADO", text_color="lime")
    return True


def _apply_project_data(app, project, show_error=True):
    try:
        app.disconnect()

        tags = [
            Tag.from_dict(tag_data)
            for tag_data in project.get("tags", [])
            if isinstance(tag_data, dict)
        ]
        names_valid, names_message = normalize_and_validate_tag_names(tags)
        if not names_valid:
            raise ValueError(names_message)

        _restore_tag_feature_configuration(tags, project)
        app.tags = tags
        app.tag_runtime.clear()

        plc = project.get("plc", {})
        brand = plc.get("brand", "Siemens")
        if brand not in SUPPORTED_BRANDS:
            raise ValueError(f"Marca PLC inválida: {brand}")

        app.brand_menu.set(brand)
        if brand == "Siemens":
            app.create_siemens_options()
        elif brand == "Schneider":
            app.create_schneider_options()
        elif brand == "Modbus TCP":
            app.create_modbus_options()
        elif brand == "Rockwell":
            app.create_rockwell_options()
        elif brand == "Omron":
            app.create_omron_options()
        else:
            app.create_simulator_options()

        update_tag_address_context(app)
        _set_entry(app.ip_entry, plc.get("ip", "192.168.1.10"))
        _restore_connection_settings(app, brand, plc.get("settings", {}))

        refresh_tag_table(app)
        app.generate_signals()

        _restore_digital_settings(
            app,
            project.get("runtime_settings", {}).get("digital_inputs", []),
        )
        _restore_analog_profiles(app, project.get("analog_profiles", []))
        _restore_pid(app, project.get("pid", {}))
        reload_alarms(app, project.get("alarms", []))
        _restore_trends(app, project.get("trends", {}))

        from ui.dashboard_tab import clear_dashboard_events, update_dashboard
        clear_dashboard_events(app)
        update_dashboard(app, "Projeto carregado")
        return True
    except Exception as error:
        if show_error:
            messagebox.showerror("Erro ao aplicar projeto", str(error))
        return False


def _restore_tag_feature_configuration(tags, project):
    trends = project.get("trends", {})
    if "enabled_tags" in trends:
        enabled = set(trends.get("enabled_tags", []))
        for tag in tags:
            tag.enabled_trend = tag.name in enabled

    dashboard = project.get("dashboard", {})
    if "enabled_tags" in dashboard:
        enabled = set(dashboard.get("enabled_tags", []))
        for tag in tags:
            tag.enabled_dashboard = tag.name in enabled


def _restore_connection_settings(app, brand, settings):
    if brand == "Siemens":
        _set_entry(app.rack_entry, settings.get("rack", "0"))
        _set_entry(app.slot_entry, settings.get("slot", "1"))
        _set_entry(app.db_entry, settings.get("db_number", "100"))
        return

    if brand == "Modbus TCP":
        _set_entry(app.port_entry, settings.get("port", "502"))
        _set_entry(app.slave_entry, settings.get("slave_id", "1"))
        return

    if brand == "Rockwell":
        return

    if brand == "Simulator":
        return

    if brand == "Omron":
        _set_entry(app.port_entry, settings.get("port", "9600"))
        _set_entry(
            app.destination_node_entry,
            settings.get("destination_node", "0"),
        )
        _set_entry(app.source_node_entry, settings.get("source_node", "1"))
        return

    model = settings.get("model", "M221")
    if model not in SCHNEIDER_MODELS:
        model = "M221"
    app.schneider_model_menu.set(model)
    _set_entry(app.port_entry, settings.get("port", "502"))
    _set_entry(app.slave_entry, settings.get("slave_id", "1"))
    _set_entry(app.coil_start_entry, settings.get("coil_start", "0"))
    _set_entry(app.reg_start_entry, settings.get("register_start", "0"))
    app.schneider_info.configure(text=SCHNEIDER_MODELS[model]["description"])


def _restore_digital_settings(app, settings):
    by_tag = {
        str(item.get("tag", "")): item
        for item in settings
        if isinstance(item, dict)
    }
    for index, widget in enumerate(app.digital_widgets):
        config = by_tag.get(widget["tag"].name)
        if config is None:
            continue
        mode = config.get("mode", "Toggle")
        widget["mode_menu"].set(mode if mode in ("Toggle", "Pulse") else "Toggle")
        _set_entry(widget["pulse_entry"], config.get("pulse_ms", "500"))
        app.update_digital_name(index)


def _restore_analog_profiles(app, profiles):
    by_tag = {
        str(item.get("tag", "")): item
        for item in profiles
        if isinstance(item, dict)
    }
    for widget in app.analog_widgets:
        config = by_tag.get(widget["tag"].name)
        if config is None:
            continue
        mode = config.get("mode", "Manual")
        widget["profile_mode"].set(
            mode if mode in ("Manual", "Ramp", "Random", "Step") else "Manual"
        )
        _set_entry(widget["min_entry"], config.get("min", "0"))
        _set_entry(widget["max_entry"], config.get("max", "27648"))
        _set_entry(widget["step_entry"], config.get("step", "500"))
        _set_entry(widget["interval_entry"], config.get("interval_ms", "500"))
        widget["profile_status"].configure(text="MANUAL", text_color="gray")


def _restore_pid(app, pid):
    app.stop_pid()
    defaults = {
        "sp": "10000",
        "kp": "1.0",
        "ki": "0.0",
        "kd": "0.0",
        "out_min": "0",
        "out_max": "27648",
        "interval_ms": "500",
    }
    entries = {
        "sp": app.pid_sp_entry,
        "kp": app.pid_kp_entry,
        "ki": app.pid_ki_entry,
        "kd": app.pid_kd_entry,
        "out_min": app.pid_out_min_entry,
        "out_max": app.pid_out_max_entry,
        "interval_ms": app.pid_interval_entry,
    }
    for field, entry in entries.items():
        _set_entry(entry, pid.get(field, defaults[field]))

    numeric_names = [tag.name for tag in get_numeric_tags(app)]
    output_tags = get_pid_output_tags(app)
    output_names = [tag.name for tag in output_tags]

    sp_source = str(pid.get("sp_source", "Manual") or "Manual")
    app.pid_sp_source_menu.set(
        sp_source if sp_source in numeric_names else "Manual"
    )

    pv_source = str(pid.get("pv_source", "") or "")
    app.pid_pv_menu.set(
        pv_source if pv_source in numeric_names
        else (numeric_names[0] if numeric_names else "")
    )

    out_source = str(pid.get("out_source", "") or "")
    if out_source not in output_names:
        legacy_address = _normalize_pid_address(pid.get("out_address", ""))
        out_source = next(
            (
                tag.name for tag in output_tags
                if _normalize_pid_address(tag.address) == legacy_address
            ),
            "",
        )
    app.pid_out_menu.set(
        out_source if out_source in output_names
        else (output_names[0] if output_names else "")
    )


def _restore_trends(app, trends):
    if (
        hasattr(app, "ensure_trend_tab")
        and not getattr(app, "_trend_initialized", False)
    ):
        app._pending_trend_settings = copy.deepcopy(trends)
        return
    from ui.trend_tab import clear_trend, refresh_trend_selectors, stop_trend

    stop_trend(app)
    clear_trend(app)
    app.trend_auto_scale.set(bool(trends.get("auto_scale", True)))
    refresh_trend_selectors(app)

    selected = set(trends.get("selected_curves", []))
    for name, variable in app.trend_tag_vars.items():
        variable.set(name in selected)


def _default_project_data():
    return {
        "format": PROJECT_FORMAT,
        "version": PROJECT_VERSION,
        "plc": {
            "brand": "Siemens",
            "ip": "192.168.1.10",
            "settings": {
                "rack": "0",
                "slot": "1",
                "db_number": "100",
            },
        },
        "tags": [],
        "runtime_settings": {"digital_inputs": []},
        "alarms": [],
        "pid": {},
        "trends": {
            "enabled_tags": [],
            "selected_curves": [],
            "auto_scale": True,
        },
        "dashboard": {"enabled_tags": []},
        "analog_profiles": [],
    }


def _stage_project_data(project):
    _validate_project_data(project)
    staged = copy.deepcopy(project)

    plc = staged.get("plc")
    if not isinstance(plc, dict):
        raise ValueError("Configuração PLC inválida")
    brand = plc.get("brand", "Siemens")
    if brand not in SUPPORTED_BRANDS:
        raise ValueError(f"Marca PLC inválida: {brand}")
    if not isinstance(plc.get("settings", {}), dict):
        raise ValueError("Definições de ligação PLC inválidas")

    tags = []
    for index, tag_data in enumerate(staged.get("tags", []), start=1):
        if not isinstance(tag_data, dict):
            raise ValueError(f"Tag {index}: definição inválida")
        tag = Tag.from_dict(tag_data)
        if tag.data_type not in ("BOOL", "INT", "REAL"):
            raise ValueError(f"Tag {index}: tipo inválido {tag.data_type}")
        if tag.direction not in ("Input", "Feedback", "Output", "Internal"):
            raise ValueError(f"Tag {index}: direção inválida {tag.direction}")
        if not isinstance(tag.address, str) or not tag.address.strip():
            raise ValueError(f"Tag {index}: endereço vazio")
        tag.address = tag.address.strip()
        if brand not in ("Rockwell", "Simulator"):
            tag.address = tag.address.upper()
        tags.append(tag)

    names_valid, names_message = normalize_and_validate_tag_names(tags)
    if not names_valid:
        raise ValueError(names_message)
    staged["tags"] = [tag.to_dict() for tag in tags]

    section_types = {
        "runtime_settings": dict,
        "pid": dict,
        "trends": dict,
        "dashboard": dict,
        "alarms": list,
        "analog_profiles": list,
    }
    for section, expected_type in section_types.items():
        value = staged.get(section, expected_type())
        if not isinstance(value, expected_type):
            raise ValueError(f"Secção de projeto inválida: {section}")
        staged[section] = value

    runtime_settings = staged["runtime_settings"]
    if not isinstance(runtime_settings.get("digital_inputs", []), list):
        raise ValueError("Configuração de entradas digitais inválida")

    tag_types = {tag.name: tag.data_type for tag in tags}
    normalized_alarms = []
    for index, alarm in enumerate(staged["alarms"], start=1):
        if not isinstance(alarm, dict):
            raise ValueError(f"Alarme {index}: configuração inválida")
        source = str(alarm.get("source", "")).strip()
        alarm_type = alarm.get("type", "HIGH")
        if alarm_type not in ("HIGH HIGH", "HIGH", "LOW", "LOW LOW"):
            raise ValueError(f"Alarme {index}: tipo inválido {alarm_type}")
        try:
            numeric_limit = float(alarm.get("limit", 20000))
        except (TypeError, ValueError) as error:
            raise ValueError(f"Alarme {index}: limite inválido") from error
        if tag_types.get(source) != "REAL" and numeric_limit.is_integer():
            numeric_limit = int(numeric_limit)
        normalized_alarms.append({
            "source": source,
            "type": alarm_type,
            "limit": numeric_limit,
        })
    staged["alarms"] = normalized_alarms

    return staged


def _validate_project_data(project):
    if not isinstance(project, dict):
        raise ValueError("Formato de projeto inválido")
    if project.get("format") != PROJECT_FORMAT:
        raise ValueError("O ficheiro não é um projeto do PLC Simulator")
    if project.get("version") != PROJECT_VERSION:
        raise ValueError(f"Versão de projeto não suportada: {project.get('version')}")
    if "plc" not in project:
        raise ValueError("Configuração PLC em falta")
    if not isinstance(project.get("tags", []), list):
        raise ValueError("Lista de tags inválida")


def _project_path(file_path):
    path = str(file_path)
    if not path.lower().endswith(PROJECT_EXTENSION):
        path += PROJECT_EXTENSION
    return path


def _set_entry(entry, value):
    entry.delete(0, "end")
    entry.insert(0, str(value))


def _update_project_title(app):
    file_path = getattr(app, "project_path", None)
    project_name = os.path.basename(file_path) if file_path else "Novo Projeto"
    app.app.title(f"PLC Simulator Universal — {project_name}")
    update_top_status_bar(app)


def _normalize_pid_address(address):
    return (
        str(address)
        .strip()
        .upper()
        .replace("DBW", "")
        .replace("DBD", "")
        .replace("%MW", "")
        .replace("MW", "")
    )


def reload_alarms(app, alarms):
    if not hasattr(app, "alarms"):
        return

    from ui.alarm_tab import (
        create_alarm_row,
        normalize_alarm_limit,
        update_alarm_status,
    )
    from ui.tag_manager import get_alarm_tags

    for row in app.alarm_rows:
        container = row["state"].master
        if container.winfo_exists():
            container.destroy()

    app.alarms.clear()
    app.alarm_rows.clear()
    enabled_sources = [tag.name for tag in get_alarm_tags(app)]

    for alarm_config in alarms:
        if not isinstance(alarm_config, dict):
            continue
        source = str(alarm_config.get("source", ""))
        if source not in enabled_sources:
            continue
        alarm_type = alarm_config.get("type", "HIGH")
        if alarm_type not in ("HIGH HIGH", "HIGH", "LOW", "LOW LOW"):
            alarm_type = "HIGH"

        alarm = {
            "source": source,
            "type": alarm_type,
            "limit": normalize_alarm_limit(
                app,
                source,
                alarm_config.get("limit", 20000),
            ),
            "active": False,
            "ack": False,
            "last_value": 0,
            "timestamp": "-",
        }
        app.alarms.append(alarm)
        create_alarm_row(app, alarm)

    update_alarm_status(app)
