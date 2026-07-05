import os
import logging
import time
import customtkinter as ctk
from tkinter import messagebox

from core.tag_runtime import RuntimeTagCache, RuntimeValueSource
from services.plc_service import PLCService
from services.settings_service import ApplicationSettings

from ui.header import create_header, SCHNEIDER_MODELS
from ui.digital_tab import create_digital_row
from ui.analog_tab import create_analog_row
from ui.pid_tab import create_pid_tab
from ui.pid_logic import start_pid as pid_start
from ui.pid_logic import stop_pid as pid_stop
from ui.pid_logic import run_pid_loop as pid_run_loop
from ui.pid_logic import write_pid_output as pid_write_output
from ui.project_config import (
    build_project_data,
    new_project,
    open_project,
    open_project_path,
    save_project,
    save_project_as,
)
from ui.dashboard_tab import create_dashboard_tab, update_dashboard
from ui.alarm_tab import create_alarm_tab, update_alarm_sources
from ui.tag_manager import (
    create_tag_manager_tab,
    get_input_analog_tags,
    get_input_bool_tags,
    get_invalid_tags_for_brand,
    get_numeric_tags,
    get_pid_output_tags,
    refresh_tag_table,
    update_tag_address_context,
    update_csv_button_visibility,
)
from ui.feedback_tab import (
    create_feedback_tab,
    refresh_feedback_table,
    update_feedback_values,
)
from ui.scrollable_frame import SafeScrollableFrame

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

LOGGER = logging.getLogger(__name__)
APP_VERSION = "2.2"
NO_RECENT_PROJECTS = "Nenhum projeto recente"


class PLCSimulator:
    def __init__(self):
        os.makedirs("configs", exist_ok=True)

        self.settings = ApplicationSettings.load()

        self.tag_runtime = RuntimeTagCache()
        self.plc_service = PLCService(runtime_cache=self.tag_runtime)
        self.digital_states = {}
        self.digital_controls = []
        self.digital_tags = []
        self.pending_pulse_callbacks = {}
        self.analog_controls = []
        self.analog_tags = []
        self.analog_profile_directions = {}
        self.analog_profile_running = {}
        self.project_path = None
        self._trend_initialized = False

        self.cyclic_read_enabled = False

        self.pid_running = False
        self.pid_integral = 0.0
        self.pid_last_error = 0.0
        self.pid_last_time = time.time()

        self.app = ctk.CTk()
        self.app.title("PLC Simulator Universal — Novo Projeto")
        self.app.geometry(self.settings.window_size)
        self.app.minsize(1200, 750)
        self.app.protocol("WM_DELETE_WINDOW", self.on_close)

        self.create_header()
        self.create_tabs()
        self.ip_entry.delete(0, "end")
        self.ip_entry.insert(0, self.settings.ip_address)
        self.brand_menu.set(self.settings.plc_brand)
        self.update_brand(self.settings.plc_brand)
        self.refresh_recent_projects()
        self._mark_project_saved()

    def create_header(self):
        create_header(self)

    def create_tabs(self):
        self.tabs = ctk.CTkTabview(
            self.app,
            command=self._on_tab_changed,
        )
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_dashboard = self.tabs.add("Dashboard")
        self.tab_tags = self.tabs.add("Tag Manager")
        self.tab_digital = self.tabs.add("Entradas Digitais")
        self.tab_analog = self.tabs.add("Entradas Analógicas")
        self.tab_pid = self.tabs.add("PID")
        self.tab_trends = self.tabs.add("Trends")
        self.tab_alarms = self.tabs.add("Alarmes")
        self.tab_feedbacks = self.tabs.add("Feedbacks")

        create_dashboard_tab(self)
        create_tag_manager_tab(self)
        create_feedback_tab(self)

        self.digital_scroll = SafeScrollableFrame(self.tab_digital)
        self.digital_scroll.pack(fill="both", expand=True, padx=10, pady=10)

        self.analog_scroll = SafeScrollableFrame(self.tab_analog)
        self.analog_scroll.pack(fill="both", expand=True, padx=10, pady=10)

        self.create_pid_tab()
        create_alarm_tab(self)

    def _on_tab_changed(self):
        if self.tabs.get() == "Trends":
            self.ensure_trend_tab()

    def ensure_trend_tab(self):
        if self._trend_initialized:
            return
        from ui.trend_tab import create_trend_tab

        create_trend_tab(self)
        self._trend_initialized = True
        pending = getattr(self, "_pending_trend_settings", None)
        if pending is not None:
            del self._pending_trend_settings
            from ui.project_config import _restore_trends

            _restore_trends(self, pending)

    def create_pid_tab(self):
        create_pid_tab(self)

    def write_pid_output(self, value):
        return pid_write_output(self, value)

    def start_pid(self):
        pid_start(self)

    def stop_pid(self):
        pid_stop(self)

    def run_pid_loop(self):
        pid_run_loop(self)

    def connect(self):
        ip = self.ip_entry.get().strip()
        brand = self.brand_menu.get()

        try:
            if brand == "Simulator":
                result = self.plc_service.connect(brand, "")
            elif brand == "Siemens":
                result = self.plc_service.connect(
                    brand,
                    ip,
                    rack=self.rack_entry.get(),
                    slot=self.slot_entry.get(),
                    db_number=self.db_entry.get(),
                )
            elif brand in ("Schneider", "Modbus TCP"):
                result = self.plc_service.connect(
                    brand,
                    ip,
                    port=self.port_entry.get(),
                    slave_id=self.slave_entry.get(),
                )
            elif brand == "Omron":
                result = self.plc_service.connect(
                    brand,
                    ip,
                    port=self.port_entry.get(),
                    destination_node=self.destination_node_entry.get(),
                    source_node=self.source_node_entry.get(),
                )
            else:
                result = self.plc_service.connect(brand, ip)

            if result:
                status = "● SIMULATOR" if brand == "Simulator" else "● LIGADO"
                self.status_label.configure(text=status, text_color="lime")
                self.cyclic_read_enabled = True
                self.start_cyclic_read()
                event = (
                    "Simulador interno ligado"
                    if brand == "Simulator"
                    else "PLC ligado"
                )
                update_dashboard(self, event)
            else:
                self.status_label.configure(text="● ERRO LIGAÇÃO", text_color="orange")

        except Exception as e:
            self.status_label.configure(text="● ERRO", text_color="orange")
            messagebox.showerror("Erro de ligação", str(e))

    def disconnect(self):
        self.cyclic_read_enabled = False

        if hasattr(self, "trend_running"):
            from ui.trend_tab import stop_trend

            stop_trend(self)

        self.stop_pid()

        self.plc_service.disconnect()

        self.status_label.configure(text="● DESLIGADO", text_color="red")
        update_dashboard(self, "PLC desligado")

    def is_connected(self):
        if not self.plc_service.is_connected():
            self.status_label.configure(text="● PLC NÃO LIGADO", text_color="red")
            return False

        return True

    def is_online(self):
        return self.plc_service.is_connected()

    def update_brand(self, value):
        self.disconnect()

        if value == "Siemens":
            self.create_siemens_options()
        elif value == "Schneider":
            self.create_schneider_options()
        elif value == "Modbus TCP":
            self.create_modbus_options()
        elif value == "Rockwell":
            self.create_rockwell_options()
        elif value == "Omron":
            self.create_omron_options()
        else:
            self.create_simulator_options()

        update_csv_button_visibility(self)
        update_tag_address_context(self)
        self.generate_signals()

    def update_schneider_model(self, model):
        defaults = SCHNEIDER_MODELS[model]

        self.coil_start_entry.delete(0, "end")
        self.coil_start_entry.insert(0, str(defaults["coil_start"]))

        self.reg_start_entry.delete(0, "end")
        self.reg_start_entry.insert(0, str(defaults["reg_start"]))

        self.schneider_info.configure(text=defaults["description"])
        self.generate_signals()

    def clear_signal_frames(self):
        for callback_id in self.pending_pulse_callbacks.values():
            self.app.after_cancel(callback_id)
        self.pending_pulse_callbacks.clear()

        for widget in self.digital_scroll.winfo_children():
            widget.destroy()

        for widget in self.analog_scroll.winfo_children():
            widget.destroy()

        self.digital_states.clear()
        self.digital_controls.clear()
        self.digital_tags.clear()
        self.analog_controls.clear()
        self.analog_tags.clear()
        self.analog_profile_running.clear()
        self.analog_profile_directions.clear()

    def generate_signals(self):
        self.tag_runtime.sync(getattr(self, "tags", []))
        invalid_tags = get_invalid_tags_for_brand(self)
        for tag in invalid_tags:
            self.tag_runtime.invalidate(tag.name)

        self.clear_signal_frames()

        for i, tag in enumerate(get_input_bool_tags(self)):
            create_digital_row(self, i, tag=tag)

        for i, tag in enumerate(get_input_analog_tags(self)):
            create_analog_row(self, i, tag=tag)

        if hasattr(self, "feedback_table"):
            refresh_feedback_table(self)

        self.update_pid_sources()

        if hasattr(self, "trend_selector_frame"):
            from ui.trend_tab import refresh_trend_selectors

            refresh_trend_selectors(self)

        if hasattr(self, "alarm_source_menu"):
            update_alarm_sources(self)

        if hasattr(self, "tag_table"):
            refresh_tag_table(self)

        update_tag_address_context(self)
        update_dashboard(self, "Sinais gerados")

        if invalid_tags:
            self.status_label.configure(
                text=f"● {len(invalid_tags)} TAG(S) INCOMPATÍVEL(IS)",
                text_color="orange",
            )
    
    def update_pid_sources(self):
        if not hasattr(self, "pid_pv_menu") or not hasattr(self, "pid_out_menu"):
            return

        numeric_names = [tag.name for tag in get_numeric_tags(self)]
        output_names = [tag.name for tag in get_pid_output_tags(self)]

        current_sp = self.pid_sp_source_menu.get()
        current_pv = self.pid_pv_menu.get()
        current_out = self.pid_out_menu.get()

        sp_sources = ["Manual"] + numeric_names
        self.pid_sp_source_menu.configure(values=sp_sources)
        self.pid_sp_source_menu.set(
            current_sp if current_sp in sp_sources else "Manual"
        )

        self.pid_pv_menu.configure(values=numeric_names)
        self.pid_pv_menu.set(
            current_pv if current_pv in numeric_names
            else (numeric_names[0] if numeric_names else "")
        )

        self.pid_out_menu.configure(values=output_names)
        self.pid_out_menu.set(
            current_out if current_out in output_names
            else (output_names[0] if output_names else "")
        )

    def update_digital_name(self, index):
        item = self.digital_controls[index]
        name = item["name_entry"].get()
        state = self.digital_states.get(index, False)
        item["button"].configure(text=f"{name} {'ON' if state else 'OFF'}")

    def digital_action(self, index):
        item = self.digital_controls[index]
        mode = item["mode_menu"].get()

        if mode == "Pulse":
            self.pulse_digital(index)
        else:
            self.toggle_digital(index)

    def pulse_digital(self, index):
        item = self.digital_controls[index]
        tag = self.digital_tags[index]

        try:
            pulse_ms = int(item["pulse_entry"].get())
        except ValueError:
            pulse_ms = 500

        if pulse_ms < 50:
            pulse_ms = 50

        self.write_digital_state(index, True)

        tag_identity = id(tag)
        previous_callback = self.pending_pulse_callbacks.pop(tag_identity, None)
        if previous_callback is not None:
            self.app.after_cancel(previous_callback)

        callback_id = self.app.after(
            pulse_ms,
            lambda: self._finish_digital_pulse(tag)
        )
        self.pending_pulse_callbacks[tag_identity] = callback_id

    def _finish_digital_pulse(self, tag):
        self.pending_pulse_callbacks.pop(id(tag), None)
        for index, candidate in enumerate(self.digital_tags):
            if candidate is tag:
                self.write_digital_state(index, False)
                return

    def toggle_digital(self, index):
        tag = self.digital_tags[index]
        current_state = bool(
            self.tag_runtime.get_value(tag.name, False)
        )
        new_state = not current_state
        self.write_digital_state(index, new_state)

    def write_digital_state(self, index, state):
        tag = self.digital_tags[index]

        if not self.is_online():
            self.update_digital_ui(
                index,
                bool(state),
                source=RuntimeValueSource.SIMULATION,
            )
            self.status_label.configure(
                text="● SIMULAÇÃO OFFLINE",
                text_color="cyan",
            )
            update_dashboard(
                self,
                f"Digital {tag.name} = {'ON' if state else 'OFF'} (simulation)",
            )
            return bool(state)

        real_state = self.plc_service.write_bool(tag, state)

        if real_state is None:
            self.status_label.configure(text="● ERRO ESCRITA", text_color="orange")
            return None

        self.update_digital_ui(
            index,
            real_state,
        )
        self.status_label.configure(text="● ESCRITA + LEITURA OK", text_color="lime")
        update_dashboard(
            self,
            f"Digital {tag.name} = {'ON' if real_state else 'OFF'} (PLC)",
        )

        return real_state

    def update_analog(self, index, value):
        item = self.analog_controls[index]
        tag = self.analog_tags[index]

        if item["profile_mode"].get() != "Manual":
            current_value = self.tag_runtime.get_value(tag.name, 0)
            item["slider"].set(current_value)
            return

        self.write_analog_by_index(index, int(float(value)))

    def write_analog_by_index(self, index, value):
        tag = self.analog_tags[index]

        if not self.is_online():
            self.update_analog_ui(
                index,
                value,
                source=RuntimeValueSource.SIMULATION,
            )
            self.status_label.configure(
                text="● SIMULAÇÃO OFFLINE",
                text_color="cyan",
            )
            update_dashboard(
                self,
                f"Process value {tag.name} = {value} (simulation)",
            )
            return value

        real_value = self.plc_service.write_numeric(tag, value)

        if real_value is None:
            self.status_label.configure(text="● ERRO ESCRITA", text_color="orange")
            return None

        self.update_analog_ui(
            index,
            real_value,
        )
        self.status_label.configure(text="● ESCRITA + LEITURA OK", text_color="lime")
        update_dashboard(
            self,
            f"Process value {tag.name} = {real_value} (PLC)",
        )

        return real_value

    def start_cyclic_read(self):
        if not self.cyclic_read_enabled:
            return

        if not self.is_connected():
            self.cyclic_read_enabled = False
            self.tag_runtime.invalidate_source(RuntimeValueSource.PLC)
            update_feedback_values(self)
            update_dashboard(self, "PLC desligado")
            return

        try:
            self.plc_service.read(self.tags)
            self.update_runtime_widgets()
            update_feedback_values(self)
            update_dashboard(self)

        except Exception as e:
            self.status_label.configure(text="● ERRO LEITURA", text_color="orange")
            LOGGER.exception("Cyclic PLC read failed")

        self.app.after(500, self.start_cyclic_read)

    def update_runtime_widgets(self):
        for index, tag in enumerate(self.digital_tags):
            value = self.tag_runtime.get_value(tag.name)
            if value is not None:
                self.update_digital_ui(index, bool(value))

        for index, tag in enumerate(self.analog_tags):
            value = self.tag_runtime.get_value(tag.name)
            if value is not None:
                self.update_analog_ui(index, value)

    def update_digital_ui(self, index, state, source=None):
        item = self.digital_controls[index]
        tag = self.digital_tags[index]

        self.digital_states[index] = state
        if source is not None:
            self.tag_runtime.update(tag.name, state, source)
        name = item["name_entry"].get()

        item["button"].configure(text=f"{name} {'ON' if state else 'OFF'}")
        item["led"].configure(text="●", text_color="lime" if state else "gray")
        item["live"].configure(text="1" if state else "0")

    def update_analog_ui(self, index, value, source=None):
        item = self.analog_controls[index]
        tag = self.analog_tags[index]

        if source is not None:
            self.tag_runtime.update(tag.name, value, source)
        item["slider"].set(value)
        item["value_label"].configure(text=f"{value} RAW")
        item["live"].configure(text=str(value))

    def reset_all(self):
        if not self.is_connected():
            return

        if hasattr(self, "trend_running"):
            from ui.trend_tab import stop_trend

            stop_trend(self)

        self.stop_pid()

        for i, _item in enumerate(self.digital_controls):
            self.write_digital_state(i, False)

        for i, _item in enumerate(self.analog_controls):
            self.write_analog_by_index(i, 0)

        self.status_label.configure(text="● RESET OK", text_color="lime")
        update_dashboard(self, "Reset executado")

    def save_project(self):
        result = save_project(self)
        if result:
            self._after_project_saved()
        return result

    def save_project_as(self):
        result = save_project_as(self)
        if result:
            self._after_project_saved()
        return result

    def new_project(self):
        result = new_project(self)
        if result:
            self._mark_project_saved()
        return result

    def open_project(self):
        result = open_project(self)
        if result:
            self._after_project_opened()
        return result

    def open_recent_project(self):
        path = self.recent_project_menu.get()
        if not path or path == NO_RECENT_PROJECTS:
            return False
        result = open_project_path(self, path)
        if result:
            self._after_project_opened()
        return result

    def _after_project_opened(self):
        self.settings.add_recent_project(self.project_path)
        self._save_settings()
        self.refresh_recent_projects()
        self._mark_project_saved()

    def _after_project_saved(self):
        # Saved projects belong in the same quick-access list as opened ones.
        if self.project_path:
            self.settings.add_recent_project(self.project_path)
            self._save_settings()
            self.refresh_recent_projects()
        self._mark_project_saved()

    def refresh_recent_projects(self):
        if not hasattr(self, "recent_project_menu"):
            return
        values = self.settings.recent_projects or [NO_RECENT_PROJECTS]
        self.recent_project_menu.configure(values=values)
        self.recent_project_menu.set(values[0])

    def _mark_project_saved(self):
        self._saved_project_snapshot = build_project_data(self)

    def has_unsaved_changes(self):
        saved = getattr(self, "_saved_project_snapshot", None)
        return saved is not None and build_project_data(self) != saved

    def _save_settings(self):
        self.settings.plc_brand = self.brand_menu.get()
        self.settings.ip_address = self.ip_entry.get()
        size = self.app.geometry().split("+", 1)[0]
        if "x" in size:
            self.settings.window_size = size
        try:
            self.settings.save()
        except OSError as error:
            LOGGER.warning("Could not save application settings: %s", error)

    def on_close(self):
        if self.has_unsaved_changes() and not messagebox.askyesno(
            "Alterações não guardadas",
            "O projeto tem alterações não guardadas. Fechar sem guardar?",
        ):
            return
        self._save_settings()
        self.app.destroy()

    def show_about(self):
        messagebox.showinfo("About", f"PLC Universal Simulator v{APP_VERSION}")

    def run(self):
        self.app.mainloop()
