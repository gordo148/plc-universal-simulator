import time
from tkinter import messagebox

from core.tag_runtime import RuntimeValueSource
from ui.dashboard_tab import update_dashboard
from ui.tag_manager import get_pid_output_tags, get_tag_by_name


def _runtime_numeric_value(app, tag_name):
    tag = get_tag_by_name(app, tag_name)
    if tag is None or tag.data_type not in ["INT", "REAL"]:
        raise ValueError(f"Tag PID inválida: {tag_name}")

    runtime = app.tag_runtime.get(tag.name)
    if runtime is None or not runtime.valid:
        raise ValueError(f"Tag PID sem valor runtime: {tag.name}")

    return float(runtime.value)


def _selected_output_tag(app):
    selected_name = app.pid_out_menu.get()
    tag = next(
        (tag for tag in get_pid_output_tags(app) if tag.name == selected_name),
        None,
    )
    if tag is None:
        raise ValueError("Selecione uma tag gravável INT/REAL para o PID")
    return tag


def write_pid_output(app, value):
    output_tag = _selected_output_tag(app)
    output_value = int(value)

    if not app.is_online():
        app.tag_runtime.update(
            output_tag.name,
            output_value,
            RuntimeValueSource.SIMULATION,
        )
        return output_value

    return app.plc_service.write_numeric(output_tag, output_value)


def start_pid(app):
    app.pid_running = True
    app.pid_integral = 0.0
    app.pid_last_error = 0.0
    app.pid_last_time = time.time()

    app.pid_status_label.configure(text="PID ON", text_color="lime")
    update_dashboard(app, "PID iniciado")
    run_pid_loop(app)


def stop_pid(app):
    app.pid_running = False

    if hasattr(app, "pid_status_label"):
        app.pid_status_label.configure(text="PID OFF", text_color="gray")

    update_dashboard(app, "PID parado")


def run_pid_loop(app):
    if not app.pid_running:
        return

    try:
        sp_source = app.pid_sp_source_menu.get()
        if sp_source == "Manual":
            sp = float(app.pid_sp_entry.get())
        else:
            sp = _runtime_numeric_value(app, sp_source)

        pv = _runtime_numeric_value(app, app.pid_pv_menu.get())
        kp = float(app.pid_kp_entry.get())
        ki = float(app.pid_ki_entry.get())
        kd = float(app.pid_kd_entry.get())
        out_min = float(app.pid_out_min_entry.get())
        out_max = float(app.pid_out_max_entry.get())
        interval_ms = int(app.pid_interval_entry.get())

        now = time.time()
        dt = now - app.pid_last_time
        if dt <= 0:
            dt = 0.001

        error = sp - pv
        app.pid_integral += error * dt
        derivative = (error - app.pid_last_error) / dt

        out = kp * error + ki * app.pid_integral + kd * derivative
        out = max(out_min, min(out_max, out))

        real_out = write_pid_output(app, int(out))

        if real_out is not None:
            app.pid_pv_label.configure(text=f"PV: {int(pv)}")
            app.pid_out_label.configure(text=f"OUT: {int(real_out)}")
            app.pid_status_label.configure(text="PID ON / OK", text_color="lime")
        else:
            app.pid_status_label.configure(text="PID ERRO", text_color="orange")

        app.pid_last_error = error
        app.pid_last_time = now

        if interval_ms < 100:
            interval_ms = 100

        app.app.after(interval_ms, lambda: run_pid_loop(app))

    except Exception as error:
        app.pid_status_label.configure(text="PID ERRO", text_color="orange")
        messagebox.showerror("Erro PID", str(error))
        stop_pid(app)
