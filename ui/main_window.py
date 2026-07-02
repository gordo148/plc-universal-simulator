import os
import time
import customtkinter as ctk
from tkinter import messagebox
from snap7.util import get_bool, get_int

from drivers.siemens_s7 import SiemensS7Driver
from drivers.schneider_modbus import SchneiderModbusDriver

from ui.header import create_header, SCHNEIDER_MODELS
from ui.digital_tab import create_digital_row
from ui.analog_tab import create_analog_row
from ui.pid_tab import create_pid_tab
from ui.pid_logic import start_pid as pid_start
from ui.pid_logic import stop_pid as pid_stop
from ui.pid_logic import run_pid_loop as pid_run_loop
from ui.pid_logic import write_pid_output as pid_write_output
from ui.project_config import save_project, load_project
from ui.dashboard_tab import create_dashboard_tab, update_dashboard
from ui.trend_tab import create_trend_tab, stop_trend, create_ai_checkboxes
from ui.alarm_tab import create_alarm_tab, update_alarm_sources
from ui.tag_manager import (
    create_tag_manager_tab,
    get_input_analog_tags,
    get_input_bool_tags,
)
from ui.feedback_tab import create_feedback_tab, refresh_feedback_table

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class PLCSimulator:
    def __init__(self):
        os.makedirs("configs", exist_ok=True)

        self.driver = None
        self.digital_states = {}
        self.digital_widgets = []
        self.analog_widgets = []
        self.analog_profile_running = {}

        self.cyclic_read_enabled = False

        self.pid_running = False
        self.pid_integral = 0.0
        self.pid_last_error = 0.0
        self.pid_last_time = time.time()

        self.app = ctk.CTk()
        self.app.title("PLC Simulator Universal")
        self.app.geometry("1500x850")
        self.app.minsize(1200, 750)

        self.create_header()
        self.create_tabs()
        self.generate_signals()

    def create_header(self):
        create_header(self)

    def create_tabs(self):
        self.tabs = ctk.CTkTabview(self.app)
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

        self.digital_scroll = ctk.CTkScrollableFrame(self.tab_digital)
        self.digital_scroll.pack(fill="both", expand=True, padx=10, pady=10)

        self.analog_scroll = ctk.CTkScrollableFrame(self.tab_analog)
        self.analog_scroll.pack(fill="both", expand=True, padx=10, pady=10)

        self.create_pid_tab()
        create_trend_tab(self)
        create_alarm_tab(self)

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

        try:
            if self.brand_menu.get() == "Siemens":
                self.driver = SiemensS7Driver()
                result = self.driver.connect(
                    ip,
                    int(self.rack_entry.get()),
                    int(self.slot_entry.get()),
                    int(self.db_entry.get())
                )
            else:
                self.driver = SchneiderModbusDriver()
                result = self.driver.connect(
                    ip,
                    int(self.port_entry.get()),
                    int(self.slave_entry.get())
                )

            if result:
                self.status_label.configure(text="● LIGADO", text_color="lime")
                self.cyclic_read_enabled = True
                self.start_cyclic_read()
                update_dashboard(self, "PLC ligado")
            else:
                self.status_label.configure(text="● ERRO LIGAÇÃO", text_color="orange")

        except Exception as e:
            self.status_label.configure(text="● ERRO", text_color="orange")
            messagebox.showerror("Erro de ligação", str(e))

    def disconnect(self):
        try:
            self.cyclic_read_enabled = False

            if hasattr(self, "trend_running"):
                stop_trend(self)

            self.stop_pid()

            if self.driver:
                self.driver.disconnect()

            self.driver = None
            self.status_label.configure(text="● DESLIGADO", text_color="red")
            update_dashboard(self, "PLC desligado")

        except Exception:
            pass

    def is_connected(self):
        if self.driver is None or not self.driver.is_connected():
            self.status_label.configure(text="● PLC NÃO LIGADO", text_color="red")
            return False

        return True

    def update_brand(self, value):
        self.disconnect()

        if value == "Siemens":
            self.create_siemens_options()
        else:
            self.create_schneider_options()

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
        for widget in self.digital_scroll.winfo_children():
            widget.destroy()

        for widget in self.analog_scroll.winfo_children():
            widget.destroy()

        self.digital_states.clear()
        self.digital_widgets.clear()
        self.analog_widgets.clear()
        self.analog_profile_running.clear()

    def generate_signals(self):
        self.clear_signal_frames()

        for i, tag in enumerate(get_input_bool_tags(self)):
            create_digital_row(self, i, tag=tag)

        for i, tag in enumerate(get_input_analog_tags(self)):
            create_analog_row(self, i, tag=tag)

        if hasattr(self, "feedback_table"):
            refresh_feedback_table(self)

        self.update_pid_sources()

        if hasattr(self, "trend_selector_frame"):
            create_ai_checkboxes(self)

        if hasattr(self, "alarm_source_menu"):
            update_alarm_sources(self)

        update_dashboard(self, "Sinais gerados")
    
    def update_pid_sources(self):
        if not hasattr(self, "pid_pv_menu"):
            return

        values = [f"AI_{i + 1:02d}" for i in range(len(self.analog_widgets))]
        if not values:
            values = ["AI_01"]

        self.pid_pv_menu.configure(values=values)
        self.pid_pv_menu.set(values[0])

    def update_digital_name(self, index):
        item = self.digital_widgets[index]
        name = item["name_entry"].get()
        state = self.digital_states.get(index, False)
        item["button"].configure(text=f"{name} {'ON' if state else 'OFF'}")

    def digital_action(self, index):
        item = self.digital_widgets[index]
        mode = item["mode_menu"].get()

        if mode == "Pulse":
            self.pulse_digital(index)
        else:
            self.toggle_digital(index)

    def pulse_digital(self, index):
        if not self.is_connected():
            return

        item = self.digital_widgets[index]

        try:
            pulse_ms = int(item["pulse_entry"].get())
        except ValueError:
            pulse_ms = 500

        if pulse_ms < 50:
            pulse_ms = 50

        self.write_digital_state(index, True)

        self.app.after(
            pulse_ms,
            lambda idx=index: self.write_digital_state(idx, False)
        )

    def toggle_digital(self, index):
        if not self.is_connected():
            return

        new_state = not self.digital_states[index]
        self.write_digital_state(index, new_state)

    def write_digital_state(self, index, state):
        if not self.is_connected():
            return None

        item = self.digital_widgets[index]

        if self.brand_menu.get() == "Siemens":
            real_state = self.driver.write_digital(
                item["address_data"]["byte"],
                item["address_data"]["bit"],
                state
            )
        else:
            real_state = self.driver.write_digital(
                item["address_data"]["coil"],
                state
            )

        if real_state is None:
            self.status_label.configure(text="● ERRO ESCRITA", text_color="orange")
            return None

        self.update_digital_ui(index, real_state)
        self.status_label.configure(text="● ESCRITA + LEITURA OK", text_color="lime")
        update_dashboard(self, "Digital alterada")

        return real_state

    def update_analog(self, index, value):
        item = self.analog_widgets[index]

        if item["profile_mode"].get() != "Manual":
            item["slider"].set(int(item["live"].cget("text")))
            return

        if not self.is_connected():
            old_value = int(item["live"].cget("text"))
            item["slider"].set(old_value)
            return

        self.write_analog_by_index(index, int(float(value)))

    def write_analog_by_index(self, index, value):
        item = self.analog_widgets[index]

        if self.brand_menu.get() == "Siemens":
            real_value = self.driver.write_analog(item["address_data"]["byte"], value)
        else:
            real_value = self.driver.write_analog(item["address_data"]["register"], value)

        if real_value is None:
            self.status_label.configure(text="● ERRO ESCRITA", text_color="orange")
            return None

        self.update_analog_ui(index, real_value)
        self.status_label.configure(text="● ESCRITA + LEITURA OK", text_color="lime")
        update_dashboard(self, "Analógica alterada")

        return real_value

    def start_cyclic_read(self):
        if not self.cyclic_read_enabled:
            return

        if not self.is_connected():
            self.cyclic_read_enabled = False
            return

        try:
            if self.brand_menu.get() == "Siemens":
                self.cyclic_read_siemens()
            else:
                self.cyclic_read_schneider()

        except Exception as e:
            self.status_label.configure(text="● ERRO LEITURA", text_color="orange")
            print(e)

        self.app.after(500, self.start_cyclic_read)

    def cyclic_read_siemens(self):
        plc_data = self.driver.read_data(1000)

        if plc_data is None:
            return

        for i, item in enumerate(self.digital_widgets):
            byte_index = item["address_data"]["byte"]
            bit_index = item["address_data"]["bit"]

            state = get_bool(plc_data, byte_index, bit_index)
            self.update_digital_ui(i, state)

        for i, item in enumerate(self.analog_widgets):
            byte_index = item["address_data"]["byte"]

            value = get_int(plc_data, byte_index)
            self.update_analog_ui(i, value)

        update_dashboard(self)

    def cyclic_read_schneider(self):
        if self.digital_widgets:
            coil_start = min(item["address_data"]["coil"] for item in self.digital_widgets)
            coil_count = len(self.digital_widgets)

            coils = self.driver.read_coils_block(coil_start, coil_count)

            if coils is not None:
                for i, item in enumerate(self.digital_widgets):
                    address = item["address_data"]["coil"]
                    offset = address - coil_start

                    if offset < len(coils):
                        state = bool(coils[offset])
                        self.update_digital_ui(i, state)

        if self.analog_widgets:
            reg_start = min(item["address_data"]["register"] for item in self.analog_widgets)
            reg_count = len(self.analog_widgets)

            regs = self.driver.read_registers_block(reg_start, reg_count)

            if regs is not None:
                for i, item in enumerate(self.analog_widgets):
                    address = item["address_data"]["register"]
                    offset = address - reg_start

                    if offset < len(regs):
                        value = regs[offset]
                        self.update_analog_ui(i, value)

        update_dashboard(self)

    def update_digital_ui(self, index, state):
        item = self.digital_widgets[index]

        self.digital_states[index] = state
        item["tag"].value = state
        name = item["name_entry"].get()

        item["button"].configure(text=f"{name} {'ON' if state else 'OFF'}")
        item["led"].configure(text="●", text_color="lime" if state else "gray")
        item["live"].configure(text="1" if state else "0")

    def update_analog_ui(self, index, value):
        item = self.analog_widgets[index]

        item["tag"].value = value
        item["slider"].set(value)
        item["value_label"].configure(text=f"{value} RAW")
        item["live"].configure(text=str(value))

    def reset_all(self):
        if not self.is_connected():
            return

        if hasattr(self, "trend_running"):
            stop_trend(self)

        self.stop_pid()

        for i, item in enumerate(self.digital_widgets):
            self.write_digital_state(i, False)

        for i, item in enumerate(self.analog_widgets):
            self.write_analog_by_index(i, 0)

        self.status_label.configure(text="● RESET OK", text_color="lime")
        update_dashboard(self, "Reset executado")

    def save_project(self):
        save_project(self)

    def load_project(self):
        load_project(self)

    def run(self):
        self.app.mainloop()
