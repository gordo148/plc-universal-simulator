import time
from tkinter import messagebox


def write_pid_output(app, value):
    if app.brand_menu.get() == "Siemens":
        byte_address = int(app.pid_out_entry.get())
        return app.driver.write_analog(byte_address, value)

    register_address = int(app.pid_out_entry.get())
    return app.driver.write_analog(register_address, value)


def start_pid(app):
    if not app.is_connected():
        return

    app.pid_running = True
    app.pid_integral = 0.0
    app.pid_last_error = 0.0
    app.pid_last_time = time.time()

    app.pid_status_label.configure(text="PID ON", text_color="lime")
    run_pid_loop(app)


def stop_pid(app):
    app.pid_running = False

    if hasattr(app, "pid_status_label"):
        app.pid_status_label.configure(text="PID OFF", text_color="gray")


def run_pid_loop(app):
    if not app.pid_running:
        return

    try:
        sp = float(app.pid_sp_entry.get())
        kp = float(app.pid_kp_entry.get())
        ki = float(app.pid_ki_entry.get())
        kd = float(app.pid_kd_entry.get())
        out_min = float(app.pid_out_min_entry.get())
        out_max = float(app.pid_out_max_entry.get())
        interval_ms = int(app.pid_interval_entry.get())

        source = app.pid_pv_menu.get()
        pv_index = int(source.split("_")[1]) - 1
        pv = float(app.analog_widgets[pv_index]["live"].cget("text"))

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

    except Exception as e:
        app.pid_status_label.configure(text="PID ERRO", text_color="orange")
        messagebox.showerror("Erro PID", str(e))
        stop_pid(app)