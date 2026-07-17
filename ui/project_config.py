import copy
import json
import logging
import os
import tempfile
from tkinter import TclError, filedialog, messagebox

from core.input_limits import (
    InputFileTooLargeError,
    MAX_PROJECT_FILE_SIZE_BYTES,
    validate_input_file_size,
)
from core.tag_identity import InvalidTagIdError, generate_tag_id, normalize_tag_id
from core.tag_model import SIEMENS_NUMERIC_TYPES, Tag
from core.tag_references import (
    TagReferenceError,
    UnresolvedTagReferenceError,
    build_tag_reference_index,
    resolve_tag_reference,
    serialize_tag_reference,
)
from drivers.siemens_address import SiemensAddressError, validate_siemens_data_type
from core.version import APP_NAME, APP_VERSION
from services.storage_paths import future_project_path, project_directory
from ui.header import (
    SCHNEIDER_MODELS, connection_brand, connection_value,
    set_connection_brand, set_connection_value,
    update_top_status_bar,
)
from ui.tag_manager import (
    get_numeric_tags,
    get_pid_output_tags,
    get_tag_by_name,
    normalize_and_validate_tag_names,
    refresh_tag_table,
    update_tag_address_context,
)
from ui.analog_profiles import canonical_analog_profile


PROJECT_EXTENSION = ".simproject"
PROJECT_FORMAT = "plc-universal-simulator-project"
PROJECT_VERSION = 1
PROJECT_SCHEMA_VERSION = 4
SUPPORTED_BRANDS = (
    "Siemens",
    "Schneider",
    "Modbus TCP",
    "Rockwell",
    "Omron",
    "Simulator",
)
LOGGER = logging.getLogger(__name__)


class ProjectTagIdentityError(ValueError):
    """Raised when project tag identities are malformed or duplicated."""


def _initial_project_directory(app):
    return project_directory()


def new_project(app):
    if not _apply_project_data(app, _stage_project_data(_default_project_data())):
        return False

    app.project_path = None
    _update_project_title(app)
    from ui.dashboard_tab import clear_dashboard_events, update_dashboard
    clear_dashboard_events(app)
    update_dashboard(app, "Novo projeto criado")
    app.status_label.configure(text="● NOVO PROJETO", text_color="lime")
    LOGGER.info("New project created")
    return True


def save_project(app):
    file_path = getattr(app, "project_path", None)
    if not file_path:
        return save_project_as(app)
    return _write_project(app, future_project_path(file_path))


def save_project_as(app):
    file_path = filedialog.asksaveasfilename(
        initialdir=_initial_project_directory(app),
        defaultextension=PROJECT_EXTENSION,
        filetypes=[("Simulator projects", f"*{PROJECT_EXTENSION}")],
        initialfile=f"project{PROJECT_EXTENSION}",
    )
    if not file_path:
        return False

    return _write_project(app, _project_path(file_path))


def open_project(app):
    file_path = filedialog.askopenfilename(
        initialdir=_initial_project_directory(app),
        filetypes=[("Simulator projects", f"*{PROJECT_EXTENSION}")],
    )
    if not file_path:
        return False

    return open_project_path(app, file_path)


def open_project_path(app, file_path):
    """Open a project from a known path, including a recent-project entry."""

    try:
        validate_input_file_size(
            file_path,
            MAX_PROJECT_FILE_SIZE_BYTES,
            "Project",
        )
        with open(file_path, "r", encoding="utf-8") as file:
            project = json.load(file)
        migrated_project = migrate_project_data(project)
        generated_ids = migrated_project.get("_identity_migration_count", 0)
        if generated_ids:
            LOGGER.info(
                "Legacy project tag IDs generated: path=%s count=%d",
                file_path,
                generated_ids,
            )
        migrated_references = migrated_project.get("_reference_migration_count", 0)
        if migrated_references:
            LOGGER.info(
                "Legacy project feature references migrated: path=%s count=%d",
                file_path,
                migrated_references,
            )
        staged_project = _stage_project_data(migrated_project)
    except InputFileTooLargeError as error:
        messagebox.showerror("Erro ao abrir projeto", str(error))
        return False
    except ProjectTagIdentityError as error:
        LOGGER.warning(
            "Project tag identity validation failed: path=%s error=%s",
            file_path,
            error,
        )
        messagebox.showerror("Erro ao abrir projeto", str(error))
        return False
    except TagReferenceError as error:
        LOGGER.warning(
            "Project feature reference validation failed: path=%s error=%s",
            file_path,
            error,
        )
        messagebox.showerror("Erro ao abrir projeto", str(error))
        return False
    except (OSError, json.JSONDecodeError, ValueError) as error:
        LOGGER.exception("Project open failed: %s", file_path)
        messagebox.showerror(
            "Erro ao abrir projeto",
            "Unable to open project. Check the file format and permissions.",
        )
        return False

    current_project = _stage_project_data(build_project_data(app))
    runtime_snapshot = app.tag_runtime.snapshot()
    current_path = getattr(app, "project_path", None)

    if not _apply_project_data(app, staged_project, project_path=str(file_path)):
        _apply_project_data(
            app,
            current_project,
            show_error=False,
            project_path=str(current_path or "<previous in-memory project>"),
        )
        app.tag_runtime.restore(runtime_snapshot, app.tags)
        app.project_path = current_path
        _update_project_title(app)
        if hasattr(app, "update_runtime_widgets"):
            app.update_runtime_widgets()
        return False

    app.project_path = file_path
    _update_project_title(app)
    app.status_label.configure(text="● PROJETO ABERTO", text_color="lime")
    LOGGER.info("Project opened: %s", file_path)
    migration_warnings = migrated_project.get("_migration_warnings", [])
    if migrated_project.get("_was_migrated"):
        message = (
            "This project was migrated in memory. The original file was not "
            f"changed; it will use schema {PROJECT_SCHEMA_VERSION} when saved."
        )
        generated_ids = migrated_project.get("_identity_migration_count", 0)
        if generated_ids:
            message += f"\n\nStable IDs were generated for {generated_ids} tag(s)."
        if migration_warnings:
            message += "\n\n" + "\n".join(migration_warnings)
        messagebox.showwarning("Project migrated", message)
    return True


def build_project_data(app):
    brand = connection_brand(app)
    tags = list(getattr(app, "tags", []))
    tag_index = build_tag_reference_index(tags)

    def tag_for_name(name):
        matches = tag_index.by_name.get(str(name), ())
        return matches[0] if len(matches) == 1 else None

    pid_settings = {
        "sp": "10000",
        "sp_source": "Manual",
        "pv_source": "",
        "out_source": "",
        "out_address": "",
        "kp": "1.0",
        "ki": "0.0",
        "kd": "0.0",
        "out_min": "0",
        "out_max": "27648",
        "interval_ms": "500",
    }
    if hasattr(app, "pid_out_menu"):
        output_tag = get_tag_by_name(app, app.pid_out_menu.get())
        sp_name = app.pid_sp_source_menu.get()
        stored_sp = getattr(app, "_pid_sp_source_tag_id", None)
        sp_tag = (
            tag_index.by_id.get(stored_sp)
            if stored_sp is not None
            else (None if sp_name == "Manual" else tag_for_name(sp_name))
        )
        stored_pv = getattr(app, "_pid_pv_source_tag_id", None)
        pv_tag = (
            tag_index.by_id.get(stored_pv)
            if stored_pv is not None
            else tag_for_name(app.pid_pv_menu.get())
        )
        stored_out = getattr(app, "_pid_out_source_tag_id", None)
        output_tag = (
            tag_index.by_id.get(stored_out)
            if stored_out is not None
            else output_tag
        )
        pid_settings = {
            "sp": app.pid_sp_entry.get(),
            "sp_source": "Manual" if sp_tag is None else None,
            "sp_source_tag_id": sp_tag.tag_id if sp_tag else None,
            "sp_source_tag_name": sp_tag.name if sp_tag else None,
            "pv_source_tag_id": pv_tag.tag_id if pv_tag else None,
            "pv_source_tag_name": pv_tag.name if pv_tag else None,
            "out_source_tag_id": output_tag.tag_id if output_tag else None,
            "out_source_tag_name": output_tag.name if output_tag else None,
            "out_address": output_tag.address if output_tag else "",
            "kp": app.pid_kp_entry.get(),
            "ki": app.pid_ki_entry.get(),
            "kd": app.pid_kd_entry.get(),
            "out_min": app.pid_out_min_entry.get(),
            "out_max": app.pid_out_max_entry.get(),
            "interval_ms": app.pid_interval_entry.get(),
        }

    connection = {
        "brand": brand,
        "ip": "" if brand == "Simulator" else connection_value(app, "ip"),
        "settings": {},
    }
    if brand == "Siemens":
        connection["settings"] = {
            "rack": connection_value(app, "rack"),
            "slot": connection_value(app, "slot"),
        }
    elif brand == "Schneider":
        connection["settings"] = {
            "model": connection_value(app, "schneider_model"),
            "port": connection_value(app, "port"),
            "slave_id": connection_value(app, "slave_id"),
            "coil_start": connection_value(app, "coil_start"),
            "register_start": connection_value(app, "register_start"),
        }
    elif brand == "Modbus TCP":
        connection["settings"] = {
            "port": connection_value(app, "port"),
            "slave_id": connection_value(app, "slave_id"),
        }
    elif brand == "Omron":
        connection["settings"] = {
            "port": connection_value(app, "omron_port"),
            "destination_node": connection_value(app, "destination_node"),
            "source_node": connection_value(app, "source_node"),
        }

    digital_inputs_by_tag = dict(getattr(app, "_digital_settings_cache", {}))
    digital_tags = getattr(app, "digital_tags", [])
    for index, item in enumerate(getattr(app, "digital_controls", [])):
        digital_inputs_by_tag[digital_tags[index].tag_id] = {
            "tag_id": digital_tags[index].tag_id,
            "tag_name": digital_tags[index].name,
            "mode": item["mode_menu"].get(),
            "pulse_ms": item["pulse_entry"].get(),
        }
    digital_inputs = []
    for item in digital_inputs_by_tag.values():
        if not isinstance(item, dict):
            continue
        tag = (
            tag_index.by_id.get(item.get("tag_id"))
            if item.get("tag_id")
            else tag_for_name(item.get("tag_name") or item.get("tag"))
        )
        if tag is not None:
            digital_inputs.append({
                **serialize_tag_reference(tag),
                "mode": item.get("mode", "Toggle"),
                "pulse_ms": item.get("pulse_ms", "500"),
            })

    if getattr(app, "analog_controls", None):
        from ui.analog_tab import commit_analog_editor_configuration
        commit_analog_editor_configuration(app, mark_dirty=False)
    analog_profiles = [
        {**dict(canonical_analog_profile(app, tag)), **serialize_tag_reference(tag)}
        for tag in tags
        if tag.direction == "Input" and tag.data_type in SIEMENS_NUMERIC_TYPES
    ]

    alarms = []
    for alarm in getattr(app, "alarms", []):
        source_tag = (
            tag_index.by_id.get(alarm.get("source_tag_id"))
            if alarm.get("source_tag_id")
            else tag_for_name(alarm.get("source", ""))
        )
        if source_tag is None:
            raise TagReferenceError("Alarm source cannot be resolved while saving.")
        alarms.append({
            "source_tag_id": source_tag.tag_id,
            "source_tag_name": source_tag.name,
            "type": alarm["type"],
            "limit": alarm["limit"],
        })

    selected_curves = set(getattr(app, "trend_visible_tags", set()))
    if not selected_curves:
        selected_curves = {
            name
            for name, variable in getattr(app, "trend_tag_vars", {}).items()
            if variable.get()
        }
    trend_auto_scale = getattr(app, "trend_auto_scale", None)
    pending_trends = getattr(app, "_pending_trend_settings", {})
    if not selected_curves and not hasattr(app, "trend_tag_vars"):
        selected_curves = set(pending_trends.get("selected_curve_ids", []))
        if not selected_curves:
            selected_curves = set(pending_trends.get("selected_curves", []))
    selected_curve_ids = sorted(
        tag.tag_id
        for tag in tags
        if tag.tag_id in selected_curves or tag.name in selected_curves
    )

    return {
        "format": PROJECT_FORMAT,
        "version": PROJECT_VERSION,
        "schema_version": PROJECT_SCHEMA_VERSION,
        "plc": connection,
        "tags": [
            tag.to_dict()
            for tag in getattr(app, "tags", [])
        ],
        "runtime_settings": {
            "digital_inputs": digital_inputs,
            "ui_state": {
                "selected_tab": app.tabs.get() if hasattr(app, "tabs") else "Dashboard",
                "digital": {
                    "selected_tag_id": (
                        getattr(app, "_digital_selected_tag_id", None)
                        or (
                            tag_for_name(getattr(app, "_digital_selected_tag_name", None)).tag_id
                            if tag_for_name(getattr(app, "_digital_selected_tag_name", None))
                            else None
                        )
                    ),
                    "sort_column": getattr(app, "_digital_sort_column", "name"),
                    "sort_descending": getattr(app, "_digital_sort_descending", False),
                    "page_size": app.digital_page_size_menu.get() if hasattr(app, "digital_page_size_menu") else "50",
                    "search": app.digital_search_entry.get() if hasattr(app, "digital_search_entry") else "",
                },
                "analog": {
                    "selected_tag_id": (
                        getattr(app, "_analog_selected_tag_id", None)
                        or (
                            tag_for_name(getattr(app, "_analog_selected_tag_name", None)).tag_id
                            if tag_for_name(getattr(app, "_analog_selected_tag_name", None))
                            else None
                        )
                    ),
                    "sort_column": getattr(app, "_analog_sort_column", "name"),
                    "sort_descending": getattr(app, "_analog_sort_descending", False),
                    "page_size": app.analog_page_size_menu.get() if hasattr(app, "analog_page_size_menu") else "50",
                    "search": app.analog_search_entry.get() if hasattr(app, "analog_search_entry") else "",
                },
            },
        },
        "alarms": alarms,
        "pid": pid_settings,
        "trends": {
            "enabled_tag_ids": [
                tag.tag_id for tag in tags
                if tag.enabled_trend
            ],
            "selected_curve_ids": selected_curve_ids,
            "auto_scale": (
                bool(trend_auto_scale.get())
                if trend_auto_scale is not None
                else bool(pending_trends.get("auto_scale", True))
            ),
        },
        "dashboard": {
            "enabled_tag_ids": [
                tag.tag_id for tag in tags
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
        LOGGER.exception("Project save failed: %s", file_path)
        if isinstance(error, (InvalidTagIdError, ProjectTagIdentityError, TagReferenceError)):
            message = f"Unable to save project because a tag identity is invalid: {error}"
        else:
            message = "Unable to save project. Check the folder permissions."
        messagebox.showerror(
            "Erro ao guardar projeto",
            message,
        )
        return False

    app.project_path = file_path
    _update_project_title(app)
    app.status_label.configure(text="● PROJETO GUARDADO", text_color="lime")
    LOGGER.info("Project saved: %s", file_path)
    return True


def _apply_project_data(app, project, show_error=True, project_path=None):
    phase = "initialization"
    try:
        phase = "stopping current runtime"
        manager = getattr(app, "analog_simulation_manager", None)
        if manager is not None:
            manager.stop_all()
        if hasattr(app, "cancel_pending_tab_refreshes"):
            app.cancel_pending_tab_refreshes()
        app.disconnect()

        phase = "creating tags"
        tags = [
            Tag.from_dict(tag_data)
            for tag_data in project.get("tags", [])
            if isinstance(tag_data, dict)
        ]
        names_valid, names_message = normalize_and_validate_tag_names(tags)
        if not names_valid:
            raise ValueError(names_message)

        phase = "restoring tag feature configuration"
        _restore_tag_feature_configuration(tags, project)
        app.tags = tags
        from ui.dashboard_tab import reset_dashboard_project_state
        reset_dashboard_project_state(app)
        app.tag_runtime.clear()
        phase = "normalizing analog profiles"
        _restore_analog_profiles(app, project.get("analog_profiles", []))

        phase = "restoring PLC connection settings"
        plc = project.get("plc", {})
        brand = plc.get("brand", "Siemens")
        if brand not in SUPPORTED_BRANDS:
            raise ValueError(f"Marca PLC inválida: {brand}")

        app.brand_menu.set(brand)
        set_connection_brand(app, brand)
        app._connection_ui_rebuilding = True
        try:
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

            if hasattr(app, "connection_state"):
                set_connection_value(app, "ip", plc.get("ip", "192.168.1.10"))
            else:
                _set_entry(app.ip_entry, plc.get("ip", "192.168.1.10"))
            _restore_connection_settings(app, brand, plc.get("settings", {}))
        finally:
            app._connection_ui_rebuilding = False
        update_tag_address_context(app)

        phase = "rebuilding tag and simulation views"
        if hasattr(app, "ensure_tag_manager_tab"):
            app.ensure_tag_manager_tab()
        refresh_tag_table(app)
        app.generate_signals()

        digital_settings = project.get("runtime_settings", {}).get("digital_inputs", [])
        if "Entradas Digitais" in getattr(app, "_dirty_tabs", set()) or getattr(
            app, "_digital_rebuilding", False
        ):
            app._pending_digital_settings = copy.deepcopy(digital_settings)
        else:
            _restore_digital_settings(app, digital_settings)
        phase = "restoring PID, alarms, trends, and UI state"
        if hasattr(app, "ensure_pid_tab"):
            app.ensure_pid_tab()
        _restore_pid(app, project.get("pid", {}))
        if hasattr(app, "ensure_alarm_tab"):
            app.ensure_alarm_tab()
        reload_alarms(app, project.get("alarms", []))
        _restore_trends(app, project.get("trends", {}))
        _restore_simulation_ui_state(
            app, project.get("runtime_settings", {}).get("ui_state", {})
        )

        phase = "refreshing dashboard"
        from ui.dashboard_tab import clear_dashboard_events, update_dashboard
        clear_dashboard_events(app)
        update_dashboard(app, "Projeto carregado")
        return True
    except Exception:
        LOGGER.exception(
            "Project apply failed: path=%s phase=%s",
            project_path or "<in-memory project>",
            phase,
        )
        if show_error:
            messagebox.showerror(
                "Erro ao aplicar projeto",
                "Unable to apply project settings. The previous project was restored.",
            )
        return False


def _restore_tag_feature_configuration(tags, project):
    trends = project.get("trends", {})
    if "enabled_tag_ids" in trends:
        enabled = set(trends.get("enabled_tag_ids", []))
        for tag in tags:
            tag.enabled_trend = tag.tag_id in enabled

    dashboard = project.get("dashboard", {})
    if "enabled_tag_ids" in dashboard:
        enabled = set(dashboard.get("enabled_tag_ids", []))
        for tag in tags:
            tag.enabled_dashboard = tag.tag_id in enabled


def _restore_connection_settings(app, brand, settings):
    if brand == "Siemens":
        if hasattr(app, "connection_state"):
            set_connection_value(app, "rack", settings.get("rack", "0"))
            set_connection_value(app, "slot", settings.get("slot", "1"))
        else:
            _set_entry(app.rack_entry, settings.get("rack", "0"))
            _set_entry(app.slot_entry, settings.get("slot", "1"))
        return

    if brand == "Modbus TCP":
        if hasattr(app, "connection_state"):
            set_connection_value(app, "port", settings.get("port", "502"))
            set_connection_value(app, "slave_id", settings.get("slave_id", "1"))
            return
        _set_entry(app.port_entry, settings.get("port", "502"))
        _set_entry(app.slave_entry, settings.get("slave_id", "1"))
        return

    if brand == "Rockwell":
        return

    if brand == "Simulator":
        return

    if brand == "Omron":
        if hasattr(app, "connection_state"):
            set_connection_value(app, "omron_port", settings.get("port", "9600"))
            set_connection_value(app, "destination_node", settings.get("destination_node", "0"))
            set_connection_value(app, "source_node", settings.get("source_node", "1"))
            return
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
    if hasattr(app, "connection_state"):
        set_connection_value(app, "schneider_model", model)
    if hasattr(app, "connection_state"):
        set_connection_value(app, "port", settings.get("port", "502"))
        set_connection_value(app, "slave_id", settings.get("slave_id", "1"))
        set_connection_value(app, "coil_start", settings.get("coil_start", "0"))
        set_connection_value(app, "register_start", settings.get("register_start", "0"))
        app.schneider_info.configure(text=SCHNEIDER_MODELS[model]["description"])
        return
    _set_entry(app.port_entry, settings.get("port", "502"))
    _set_entry(app.slave_entry, settings.get("slave_id", "1"))
    _set_entry(app.coil_start_entry, settings.get("coil_start", "0"))
    _set_entry(app.reg_start_entry, settings.get("register_start", "0"))
    app.schneider_info.configure(text=SCHNEIDER_MODELS[model]["description"])


def _restore_simulation_ui_state(app, state):
    """Restore optional UI-only state without changing the project schema version."""
    if not isinstance(state, dict):
        return
    from ui.analog_tab import refresh_analog_tab
    from ui.digital_tab import refresh_digital_tab
    for prefix, refresh in (("digital", refresh_digital_tab), ("analog", refresh_analog_tab)):
        tab_state = state.get(prefix, {})
        if not isinstance(tab_state, dict): continue
        entry = getattr(app, f"{prefix}_search_entry", None)
        if entry is not None:
            _set_entry(entry, tab_state.get("search", ""))
        menu = getattr(app, f"{prefix}_page_size_menu", None)
        size = str(tab_state.get("page_size", "50"))
        if menu is not None and size in ("25", "50", "100", "250", "All"):
            menu.set(size)
        setattr(app, f"_{prefix}_sort_column", tab_state.get("sort_column", "name"))
        setattr(app, f"_{prefix}_sort_descending", bool(tab_state.get("sort_descending", False)))
        selected_id = tab_state.get("selected_tag_id")
        selected = next(
            (tag.name for tag in getattr(app, "tags", []) if tag.tag_id == selected_id),
            None,
        )
        if selected_id is None:
            selected = tab_state.get("selected_row")
        setattr(app, f"_{prefix}_selected_tag_name", selected)
        setattr(app, f"_{prefix}_selected_tag_id", selected_id if selected else None)
        refresh(app, reset_page=True)
    selected_tab = state.get("selected_tab")
    if selected_tab and hasattr(app, "tabs"):
        try: app.tabs.set(selected_tab)
        except (ValueError, TclError): pass


def _restore_digital_settings(app, settings):
    by_tag = {
        str(item.get("tag_id", "")): item
        for item in settings
        if isinstance(item, dict)
    }
    app._digital_settings_cache = dict(by_tag)
    for index, widget in enumerate(app.digital_controls):
        config = by_tag.get(app.digital_tags[index].tag_id)
        if config is None:
            continue
        mode = config.get("mode", "Toggle")
        widget["mode_menu"].set(mode if mode in ("Toggle", "Pulse") else "Toggle")
        _set_entry(widget["pulse_entry"], config.get("pulse_ms", "500"))
        app.update_digital_name(index)


def _restore_analog_profiles(app, profiles):
    analog_tags = [
        tag for tag in getattr(app, "tags", [])
        if tag.direction == "Input" and tag.data_type in SIEMENS_NUMERIC_TYPES
    ]
    tags_by_id = {tag.tag_id: tag for tag in analog_tags}
    by_tag = {}
    if isinstance(profiles, dict):
        profiles = [
            dict(value, tag=str(name)) if isinstance(value, dict) else value
            for name, value in profiles.items()
        ]
    elif not isinstance(profiles, (list, tuple)):
        LOGGER.warning(
            "Analog profiles section normalized: type=%s expected=list",
            type(profiles).__name__,
        )
        profiles = []

    for position, item in enumerate(profiles):
        tag_id = ""
        if isinstance(item, dict):
            tag_id = str(item.get("tag_id") or "")
            if not tag_id:
                legacy_name = str(
                    item.get("tag") or item.get("tag_name") or item.get("name") or ""
                )
                matches = [tag for tag in analog_tags if tag.name == legacy_name]
                tag_id = matches[0].tag_id if len(matches) == 1 else ""
            if not tag_id:
                raw_index = item.get("index", item.get("row", position))
                try:
                    tag_id = analog_tags[int(raw_index)].tag_id
                except (TypeError, ValueError, IndexError):
                    tag_id = ""
        elif position < len(analog_tags):
            tag_id = analog_tags[position].tag_id
        if not tag_id:
            LOGGER.warning("Analog profile ignored: position=%d has no tag identity", position)
            continue
        if tag_id not in tags_by_id:
            LOGGER.warning("Analog profile ignored: tag_id=%s is not present", tag_id)
            continue
        by_tag[tag_id] = item

    # Establish the complete canonical store before any Treeview/editor refresh.
    app._analog_profile_cache = dict(by_tag)
    for tag in tags_by_id.values():
        canonical_analog_profile(app, tag)
    for index, widget in enumerate(getattr(app, "analog_controls", [])):
        if not widget.get("interactive", True):
            continue
        if index >= len(getattr(app, "analog_tags", [])):
            continue
        config = canonical_analog_profile(app, app.analog_tags[index])
        mode = config["mode"]
        widget["profile_mode"].set(
            mode if mode in ("Manual", "Ramp", "Random", "Step") else "Manual"
        )
        _set_entry(widget["min_entry"], config.get("min", "0"))
        _set_entry(widget["max_entry"], config.get("max", "27648"))
        _set_entry(widget["step_entry"], config.get("step", "500"))
        _set_entry(widget["interval_entry"], config.get("interval_ms", "500"))
    if getattr(app, "_analog_structure_initialized", False):
        from ui.analog_tab import (
            refresh_analog_tree_row,
            sync_selected_editor_from_canonical,
        )
        sync_selected_editor_from_canonical(app)
        for tag in getattr(app, "_analog_table_tags", []):
            refresh_analog_tree_row(app, tag.name)


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

    tags_by_id = {tag.tag_id: tag for tag in getattr(app, "tags", [])}
    sp_tag = tags_by_id.get(pid.get("sp_source_tag_id"))
    app._pid_sp_source_tag_id = sp_tag.tag_id if sp_tag else None
    sp_source = sp_tag.name if sp_tag else "Manual"
    app.pid_sp_source_menu.set(
        sp_source if sp_source in numeric_names else "Manual"
    )

    pv_tag = tags_by_id.get(pid.get("pv_source_tag_id"))
    app._pid_pv_source_tag_id = pv_tag.tag_id if pv_tag else None
    pv_source = pv_tag.name if pv_tag else ""
    app.pid_pv_menu.set(
        pv_source if pv_source in numeric_names
        else (numeric_names[0] if numeric_names else "")
    )

    out_tag = tags_by_id.get(pid.get("out_source_tag_id"))
    app._pid_out_source_tag_id = out_tag.tag_id if out_tag else None
    out_source = out_tag.name if out_tag else ""
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

    selected = set(trends.get("selected_curve_ids", []))
    if hasattr(app, "trend_visible_tags"):
        app.trend_visible_tags.clear()
        app.trend_visible_tags.update(selected)
        for tag in getattr(app, "tags", []):
            from ui.trend_tab import _trend_config
            _trend_config(app, tag)["visible"] = tag.tag_id in selected
        refresh_trend_selectors(app)
    else:
        for name, variable in app.trend_tag_vars.items():
            tag = next((tag for tag in getattr(app, "tags", []) if tag.name == name), None)
            variable.set(bool(tag and tag.tag_id in selected))


def _default_project_data():
    return {
        "format": PROJECT_FORMAT,
        "version": PROJECT_VERSION,
        "schema_version": PROJECT_SCHEMA_VERSION,
        "plc": {
            "brand": "Siemens",
            "ip": "192.168.1.10",
            "settings": {
                "rack": "0",
                "slot": "1",
            },
        },
        "tags": [],
        "runtime_settings": {"digital_inputs": []},
        "alarms": [],
        "pid": {},
        "trends": {
            "enabled_tag_ids": [],
            "selected_curve_ids": [],
            "auto_scale": True,
        },
        "dashboard": {"enabled_tag_ids": []},
        "analog_profiles": [],
    }


def _stage_project_data(project):
    project = migrate_project_data(project)
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
        allowed_types = ("BOOL", "BYTE", "WORD", "INT", "DWORD", "DINT", "REAL") if brand == "Siemens" else ("BOOL", "INT", "REAL")
        if tag.data_type not in allowed_types:
            raise ValueError(f"Tag {index}: tipo inválido {tag.data_type}")
        if tag.direction not in ("Input", "Feedback", "Output", "Internal"):
            raise ValueError(f"Tag {index}: direção inválida {tag.direction}")
        if not isinstance(tag.address, str) or not tag.address.strip():
            raise ValueError(f"Tag {index}: endereço vazio")
        tag.address = tag.address.strip()
        if brand == "Siemens":
            tag.address = validate_siemens_data_type(tag.data_type, tag.address).normalized_address
        elif brand not in ("Rockwell", "Simulator"):
            tag.address = tag.address.upper()
        tags.append(tag)

    names_valid, names_message = normalize_and_validate_tag_names(tags)
    if not names_valid:
        raise ValueError(names_message)
    staged["tags"] = [tag.to_dict() for tag in tags]

    raw_profiles = staged.get("analog_profiles", [])
    if raw_profiles is None:
        staged["analog_profiles"] = []
    elif isinstance(raw_profiles, dict):
        normalized_profiles = []
        for name, value in raw_profiles.items():
            if isinstance(value, dict):
                normalized_profiles.append(dict(value, tag=str(name)))
            else:
                LOGGER.warning(
                    "Analog profile normalized while staging: tag=%s type=%s",
                    name,
                    type(value).__name__,
                )
                normalized_profiles.append({"tag": str(name)})
        staged["analog_profiles"] = normalized_profiles
    elif not isinstance(raw_profiles, list):
        LOGGER.warning(
            "Analog profiles section ignored while staging: type=%s",
            type(raw_profiles).__name__,
        )
        staged["analog_profiles"] = []
    else:
        staged["analog_profiles"] = raw_profiles

    section_types = {
        "runtime_settings": dict,
        "pid": dict,
        "trends": dict,
        "dashboard": dict,
        "alarms": list,
    }
    for section, expected_type in section_types.items():
        value = staged.get(section, expected_type())
        if not isinstance(value, expected_type):
            raise ValueError(f"Secção de projeto inválida: {section}")
        staged[section] = value

    runtime_settings = staged["runtime_settings"]
    if not isinstance(runtime_settings.get("digital_inputs", []), list):
        raise ValueError("Configuração de entradas digitais inválida")

    tags_by_id = {tag.tag_id: tag for tag in tags}
    normalized_alarms = []
    for index, alarm in enumerate(staged["alarms"], start=1):
        if not isinstance(alarm, dict):
            raise ValueError(f"Alarme {index}: configuração inválida")
        source_tag_id = str(alarm.get("source_tag_id", "")).strip()
        source_tag = tags_by_id.get(source_tag_id)
        if source_tag is None:
            raise ValueError(f"Alarme {index}: referência de origem inválida")
        alarm_type = alarm.get("type", "HIGH")
        if alarm_type not in ("HIGH HIGH", "HIGH", "LOW", "LOW LOW"):
            raise ValueError(f"Alarme {index}: tipo inválido {alarm_type}")
        try:
            numeric_limit = float(alarm.get("limit", 20000))
        except (TypeError, ValueError) as error:
            raise ValueError(f"Alarme {index}: limite inválido") from error
        if source_tag.data_type != "REAL" and numeric_limit.is_integer():
            numeric_limit = int(numeric_limit)
        normalized_alarms.append({
            "source_tag_id": source_tag.tag_id,
            "source_tag_name": source_tag.name,
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


def migrate_project_data(data):
    """Return an in-memory current-schema project without modifying its source."""
    if not isinstance(data, dict):
        raise ValueError("Formato de projeto inválido")
    migrated = copy.deepcopy(data)
    schema_version = int(migrated.get("schema_version", 1) or 1)
    warnings = list(migrated.get("_migration_warnings", []))
    was_migrated = bool(migrated.get("_was_migrated", False))

    if schema_version < 2:
        plc = migrated.get("plc", {})
        if plc.get("brand", "Siemens") == "Siemens":
            settings = plc.get("settings", {})
            raw_db = settings.get("db_number", migrated.get("siemens_connection", {}).get("db_number"))
            try:
                db_number = int(raw_db)
                if db_number <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                db_number = None

            converted_tags = []
            for index, raw_tag in enumerate(migrated.get("tags", []), start=1):
                if not isinstance(raw_tag, dict):
                    warnings.append(f"Tag {index}: invalid definition was skipped.")
                    continue
                tag = copy.deepcopy(raw_tag)
                name = str(tag.get("name") or f"Tag {index}")
                data_type = str(tag.get("data_type", "BOOL")).upper()
                address = str(tag.get("address") or "").strip()
                try:
                    if address and address.lstrip().startswith("%"):
                        parsed = validate_siemens_data_type(data_type, address)
                    elif address.upper().startswith("DB") and db_number is not None:
                        parsed = validate_siemens_data_type(data_type, f"%DB{db_number}.{address}")
                    else:
                        offset = tag.get("byte_offset", tag.get("offset", tag.get("byte")))
                        if offset is None or db_number is None:
                            raise SiemensAddressError("missing legacy DB number or byte offset")
                        offset = int(offset)
                        units = {"BOOL": "DBX", "BYTE": "DBB", "WORD": "DBW", "INT": "DBW", "DWORD": "DBD", "DINT": "DBD", "REAL": "DBD"}
                        suffix = f"{offset}.{int(tag.get('bit_offset', tag.get('bit', 0)))}" if data_type == "BOOL" else str(offset)
                        parsed = validate_siemens_data_type(data_type, f"%DB{db_number}.{units[data_type]}{suffix}")
                    tag["address"] = parsed.normalized_address
                    for obsolete in ("byte_offset", "offset", "byte", "bit_offset", "bit", "db_number"):
                        tag.pop(obsolete, None)
                    converted_tags.append(tag)
                except (KeyError, TypeError, ValueError, SiemensAddressError) as error:
                    warnings.append(f'Tag "{name}": could not be migrated ({error}); tag was skipped.')
            migrated["tags"] = converted_tags
            settings.pop("db_number", None)
        was_migrated = True

    generated_ids = _normalize_project_tag_identities(migrated.get("tags", []))
    if generated_ids:
        migrated["_identity_migration_count"] = generated_ids
        was_migrated = True
    reference_count, reference_warnings = _migrate_feature_references(migrated)
    if reference_count:
        migrated["_reference_migration_count"] = reference_count
        was_migrated = True
    if reference_warnings:
        warnings.extend(reference_warnings)
        was_migrated = True
    if schema_version < PROJECT_SCHEMA_VERSION:
        was_migrated = True
        migrated["schema_version"] = PROJECT_SCHEMA_VERSION
    if was_migrated:
        migrated["_was_migrated"] = True
        migrated["_migration_warnings"] = warnings
    return migrated


def _migrate_feature_references(project):
    """Normalize all project feature references to canonical tag IDs."""
    tags = project.get("tags", [])
    if not isinstance(tags, list):
        return 0, []
    index = build_tag_reference_index(tags)
    migrated_count = 0
    warnings = []

    def resolve(reference, context, *, optional=False):
        try:
            tag = resolve_tag_reference(reference, index, context=context)
        except TagReferenceError as error:
            if not optional or not isinstance(error, UnresolvedTagReferenceError):
                raise
            warnings.append(str(error) + " Optional reference was cleared.")
            return None
        return tag

    def normalize_id_list(section, id_field, legacy_field, context):
        nonlocal migrated_count
        raw_ids = section.get(id_field)
        references = (
            [{"tag_id": value} for value in raw_ids]
            if isinstance(raw_ids, list)
            else list(section.get(legacy_field, []))
        )
        normalized = []
        for position, reference in enumerate(references, start=1):
            tag = resolve(reference, f"{context} {position}", optional=True)
            if tag is not None:
                tag_id = normalize_tag_id(tag.get("tag_id"))
                if tag_id not in normalized:
                    normalized.append(tag_id)
        if legacy_field in section:
            migrated_count += len(references)
            section.pop(legacy_field, None)
        section[id_field] = normalized

    dashboard = project.setdefault("dashboard", {})
    if isinstance(dashboard, dict):
        normalize_id_list(
            dashboard, "enabled_tag_ids", "enabled_tags", "Dashboard reference"
        )

    trends = project.setdefault("trends", {})
    if isinstance(trends, dict):
        normalize_id_list(trends, "enabled_tag_ids", "enabled_tags", "Trend enabled reference")
        normalize_id_list(trends, "selected_curve_ids", "selected_curves", "Trend curve reference")

    normalized_alarms = []
    for position, alarm in enumerate(project.get("alarms", []), start=1):
        if not isinstance(alarm, dict):
            continue
        reference = (
            {"tag_id": alarm.get("source_tag_id")}
            if "source_tag_id" in alarm
            else alarm.get("source")
        )
        if "source" in alarm and "source_tag_id" not in alarm:
            migrated_count += 1
        tag = resolve(reference, f"Alarm {position} source")
        normalized_alarms.append({
            **{key: value for key, value in alarm.items() if key not in ("source", "source_tag_id", "source_tag_name")},
            "source_tag_id": normalize_tag_id(tag.get("tag_id")),
            "source_tag_name": str(tag.get("name", "")),
        })
    project["alarms"] = normalized_alarms

    pid = project.setdefault("pid", {})
    if isinstance(pid, dict):
        for role in ("sp_source", "pv_source", "out_source"):
            id_field = f"{role}_tag_id"
            name_field = f"{role}_tag_name"
            legacy = pid.get(role)
            if role == "sp_source" and legacy == "Manual" and not pid.get(id_field):
                pid[id_field] = None
                pid[name_field] = None
                continue
            reference = {"tag_id": pid.get(id_field)} if pid.get(id_field) else legacy
            if not reference:
                pid[id_field] = None
                pid[name_field] = None
                continue
            tag = resolve(reference, f"PID {role}")
            if not pid.get(id_field):
                migrated_count += 1
            pid[id_field] = normalize_tag_id(tag.get("tag_id"))
            pid[name_field] = str(tag.get("name", ""))
            pid.pop(role, None)

    runtime_settings = project.setdefault("runtime_settings", {})
    digital_inputs = runtime_settings.get("digital_inputs", []) if isinstance(runtime_settings, dict) else []
    normalized_digital = []
    for position, item in enumerate(digital_inputs, start=1):
        if not isinstance(item, dict):
            continue
        reference = {"tag_id": item.get("tag_id")} if item.get("tag_id") else item.get("tag")
        if not item.get("tag_id"):
            migrated_count += 1
        tag = resolve(reference, f"Digital setting {position}", optional=True)
        if tag is not None:
            normalized_digital.append({
                **{key: value for key, value in item.items() if key not in ("tag", "tag_id", "tag_name")},
                "tag_id": normalize_tag_id(tag.get("tag_id")),
                "tag_name": str(tag.get("name", "")),
            })
    if isinstance(runtime_settings, dict):
        runtime_settings["digital_inputs"] = normalized_digital

    profiles = project.get("analog_profiles", [])
    if isinstance(profiles, dict):
        profiles = [
            {**value, "tag": str(name)}
            for name, value in profiles.items()
            if isinstance(value, dict)
        ]
    analog_tags = [
        tag for tag in tags
        if tag.get("direction") == "Input" and tag.get("data_type") in SIEMENS_NUMERIC_TYPES
    ]
    normalized_profiles = []
    if isinstance(profiles, list):
        for position, item in enumerate(profiles):
            if not isinstance(item, dict):
                continue
            reference = (
                {"tag_id": item.get("tag_id")}
                if item.get("tag_id")
                else item.get("tag") or item.get("tag_name") or item.get("name")
            )
            if not reference and position < len(analog_tags):
                reference = {"tag_id": analog_tags[position].get("tag_id")}
            if not item.get("tag_id"):
                migrated_count += 1
            tag = resolve(reference, f"Analog profile {position + 1}", optional=True)
            if tag is not None:
                normalized_profiles.append({
                    **{key: value for key, value in item.items() if key not in ("tag", "tag_id", "tag_name", "name")},
                    "tag_id": normalize_tag_id(tag.get("tag_id")),
                    "tag_name": str(tag.get("name", "")),
                })
    project["analog_profiles"] = normalized_profiles

    if isinstance(runtime_settings, dict):
        ui_state = runtime_settings.get("ui_state", {})
        if isinstance(ui_state, dict):
            for prefix in ("digital", "analog"):
                state = ui_state.get(prefix, {})
                if not isinstance(state, dict):
                    continue
                reference = (
                    {"tag_id": state.get("selected_tag_id")}
                    if state.get("selected_tag_id")
                    else state.get("selected_row")
                )
                if reference:
                    if "selected_row" in state and not state.get("selected_tag_id"):
                        migrated_count += 1
                    tag = resolve(reference, f"{prefix.title()} selected row", optional=True)
                    state["selected_tag_id"] = (
                        normalize_tag_id(tag.get("tag_id")) if tag is not None else None
                    )
                else:
                    state["selected_tag_id"] = None
                state.pop("selected_row", None)

    return migrated_count, warnings


def _normalize_project_tag_identities(tag_definitions):
    """Normalize project IDs, generating only identities absent from legacy tags."""
    if not isinstance(tag_definitions, list):
        return 0

    seen = set()
    generated_count = 0
    for index, tag_data in enumerate(tag_definitions, start=1):
        if not isinstance(tag_data, dict):
            continue
        name = str(tag_data.get("name") or f"Tag {index}")
        if "tag_id" not in tag_data:
            tag_data["tag_id"] = generate_tag_id()
            generated_count += 1
        try:
            tag_id = normalize_tag_id(tag_data["tag_id"])
        except InvalidTagIdError as error:
            raise ProjectTagIdentityError(
                f'Tag "{name}" has an invalid tag_id: {error}'
            ) from error
        if tag_id in seen:
            raise ProjectTagIdentityError(
                f'Duplicate tag_id "{tag_id}" found for tag "{name}" '
                "(identificador duplicado)."
            )
        tag_data["tag_id"] = tag_id
        seen.add(tag_id)
    return generated_count


def _project_path(file_path):
    path = str(file_path)
    if not path.lower().endswith(PROJECT_EXTENSION):
        path += PROJECT_EXTENSION
    return path


def _set_entry(entry, value):
    entry.delete(0, "end")
    entry.insert(0, str(value))


def _update_project_title(app):
    """Update the window title while retaining application version identity."""
    file_path = getattr(app, "project_path", None)
    project_name = os.path.basename(file_path) if file_path else "Novo Projeto"
    app.app.title(f"{APP_NAME} v{APP_VERSION} — {project_name}")
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
    enabled_tags = {tag.tag_id: tag for tag in get_alarm_tags(app)}

    for alarm_config in alarms:
        if not isinstance(alarm_config, dict):
            continue
        source_tag = enabled_tags.get(alarm_config.get("source_tag_id"))
        if source_tag is None:
            continue
        source = source_tag.name
        alarm_type = alarm_config.get("type", "HIGH")
        if alarm_type not in ("HIGH HIGH", "HIGH", "LOW", "LOW LOW"):
            alarm_type = "HIGH"

        alarm = {
            "source_tag_id": source_tag.tag_id,
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
