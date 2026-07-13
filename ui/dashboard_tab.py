"""Fixed-layout industrial overview with lightweight table models."""

from collections import deque
import os
import subprocess
import time
from tkinter import messagebox, ttk

import customtkinter as ctk

from core.version import APP_VERSION
from ui.header import connection_brand, connection_value
from ui.table_utils import debounce, filter_tags, sort_tags
from ui.tag_manager import get_dashboard_tags


DASHBOARD_REFRESH_MS = 750
EVENT_LIMIT = 50
COLORS = {"green":"#22c55e", "red":"#ef4444", "amber":"#f59e0b", "neutral":"#94a3b8", "cyan":"#22d3ee"}
CARD_BG = "#182431"
BORDER = "#334155"


def dashboard_counts(app):
    tags = getattr(app, "tags", [])
    return {
        "total": len(tags),
        "simulation": sum(bool(tag.enabled_sim) for tag in tags),
        "trends": sum(bool(tag.enabled_trend) for tag in tags),
        "alarms": sum(bool(tag.enabled_alarm) for tag in tags),
        "dashboard": sum(bool(tag.enabled_dashboard) for tag in tags),
    }


def dashboard_alarm_summary(app):
    alarms = getattr(app, "alarms", [])
    active = [alarm for alarm in alarms if alarm.get("active", False)]
    unacked = [alarm for alarm in active if not alarm.get("ack", False)]
    high = [alarm for alarm in active if alarm.get("type") in ("HIGH HIGH", "LOW LOW")]
    latest = active[-1] if active else None
    cleared = next((event[2] for event in reversed(list(getattr(app,"dashboard_events",()))) if len(event) >= 3 and "alarm normal" in str(event[2]).casefold()), None)
    return {"active":len(active), "unacknowledged":len(unacked), "high_priority":len(high), "latest":latest, "latest_cleared":cleared}


def dashboard_summary_values(app):
    counts=dashboard_counts(app); connected=app.plc_service.is_connected(); brand=connection_brand(app); diagnostics=app.plc_service.diagnostics_snapshot()
    project=os.path.basename(getattr(app,"project_path","") or "No project"); endpoint="Internal Simulator" if brand=="Simulator" else connection_value(app,"ip")
    return {"PLC":("ONLINE" if connected else "OFFLINE", "green" if connected else "red"),"Brand":(brand,"neutral"),"Endpoint":(endpoint,"cyan"),"Project":(project,"neutral"),"Tags":(counts["total"],"neutral"),"Simulation":(counts["simulation"],"amber"),"Trends":(counts["trends"],"cyan"),"Alarms":(counts["alarms"],"amber"),"Dashboard":(counts["dashboard"],"cyan"),"Communication":("HEALTHY" if connected and not diagnostics["read_error_count"] else ("INACTIVE" if not connected else "DEGRADED"),"green" if connected and not diagnostics["read_error_count"] else ("neutral" if not connected else "amber")),"Last read":(_fmt_time(diagnostics["last_read_timestamp"]),"neutral"),"Read cycle":(f"{diagnostics['last_read_duration_ms']:.1f} ms","cyan")}


def filter_dashboard_tags(tags, query="", quick_filter="All", runtime=None):
    result = filter_tags(tags, query)
    if quick_filter in ("BOOL", "INT", "REAL"):
        result = [tag for tag in result if tag.data_type == quick_filter]
    elif quick_filter == "Simulated":
        result = [tag for tag in result if tag.enabled_sim]
    elif quick_filter == "PLC source":
        result = [tag for tag in result if runtime and runtime.get(tag.name) and getattr(runtime.get(tag.name).source,"value",None) == "PLC"]
    return result


def create_dashboard_tab(app):
    if getattr(app, "_dashboard_structure_created", False): return
    app._dashboard_structure_created = True
    app.dashboard_events = deque(getattr(app, "dashboard_events", ()), maxlen=EVENT_LIMIT)
    app._dashboard_sort_column, app._dashboard_sort_descending = "name", False
    app._dashboard_selected_name = None
    app._dashboard_after_jobs = set()
    app._dashboard_last_render = {}

    root = ctk.CTkFrame(app.tab_dashboard, fg_color="#0f1720")
    root.pack(fill="both", expand=True, padx=10, pady=10)
    cards = ctk.CTkFrame(root, fg_color="transparent")
    cards.pack(fill="x", pady=(0, 6))
    app.dashboard_cards = {}
    titles = ("PLC", "Brand", "Endpoint", "Project", "Tags", "Simulation", "Trends", "Alarms", "Dashboard", "Communication", "Last read", "Read cycle")
    for index, title in enumerate(titles):
        card = ctk.CTkFrame(cards, fg_color=CARD_BG, border_width=1, border_color=BORDER, corner_radius=6)
        card.grid(row=index // 6, column=index % 6, padx=3, pady=3, sticky="nsew")
        cards.grid_columnconfigure(index % 6, weight=1)
        ctk.CTkLabel(card, text=title, text_color=COLORS["neutral"], font=("Arial", 10, "bold")).pack(pady=(5, 0))
        value = ctk.CTkLabel(card, text="—", font=("Arial", 14, "bold"))
        value.pack(pady=(0, 5))
        app.dashboard_cards[title] = value

    center = ctk.CTkFrame(root, fg_color="transparent")
    center.pack(fill="both", expand=True)
    left = ctk.CTkFrame(center, fg_color=CARD_BG, border_width=1, border_color=BORDER)
    left.pack(side="left", fill="both", expand=True, padx=(0, 5))
    right = ctk.CTkFrame(center, width=360, fg_color=CARD_BG, border_width=1, border_color=BORDER)
    right.pack(side="right", fill="y", padx=(5, 0)); right.pack_propagate(False)

    controls = ctk.CTkFrame(left, fg_color="transparent")
    controls.pack(fill="x", padx=6, pady=5)
    app.dashboard_search_entry = ctk.CTkEntry(controls, width=240, placeholder_text="Search dashboard tags")
    app.dashboard_search_entry.pack(side="left", padx=3)
    app.dashboard_search_entry.bind("<KeyRelease>", lambda _e: debounce(app, "dashboard_search", 150, lambda: refresh_dashboard_table(app)))
    ctk.CTkButton(controls, text="×", width=30, command=lambda: clear_dashboard_search(app)).pack(side="left", padx=2)
    app.dashboard_filter_menu = ctk.CTkOptionMenu(controls, values=["All","BOOL","INT","REAL","Alarm active","Simulated","PLC source"], width=120, command=lambda _v: refresh_dashboard_table(app))
    app.dashboard_filter_menu.set("All"); app.dashboard_filter_menu.pack(side="left", padx=5)
    app.dashboard_count_label = ctk.CTkLabel(controls, text="No dashboard tags")
    app.dashboard_count_label.pack(side="left", padx=8)

    columns = ("status","name","address","type","value","source","alarm","trend")
    app.dashboard_tag_table = ttk.Treeview(left, columns=columns, show="headings", height=13)
    widths = {"status":70,"name":170,"address":110,"type":60,"value":90,"source":100,"alarm":90,"trend":70}
    for column in columns:
        app.dashboard_tag_table.heading(column, text=column.title(), command=lambda col=column: sort_dashboard(app, col))
        app.dashboard_tag_table.column(column, width=widths[column], anchor="center" if column != "name" else "w")
    scroll = ttk.Scrollbar(left, command=app.dashboard_tag_table.yview)
    app.dashboard_tag_table.configure(yscrollcommand=scroll.set)
    app.dashboard_tag_table.pack(side="left", fill="both", expand=True, padx=(6,0), pady=(0,6)); scroll.pack(side="right", fill="y", pady=(0,6), padx=(0,6))
    app.dashboard_tag_table.bind("<<TreeviewSelect>>", lambda _e: refresh_dashboard_detail(app))
    app.dashboard_tag_table.bind("<Double-1>", lambda _e: open_selected_dashboard_tag(app))
    app._dashboard_visible_tags = []

    ctk.CTkLabel(right, text="SELECTED TAG", font=("Arial", 12, "bold"), text_color=COLORS["cyan"]).pack(pady=(8,3))
    app.dashboard_detail_labels = {}
    for field in ("Name","Address","Type / Direction","Effective value","PLC value","Simulated value","Source / Quality","Features","Last update"):
        label = ctk.CTkLabel(right, text=f"{field}: —", anchor="w", justify="left")
        label.pack(fill="x", padx=10, pady=1); app.dashboard_detail_labels[field] = label
    app.dashboard_detail_indicator = ctk.CTkLabel(right, text="—", font=("Arial", 24, "bold"), text_color=COLORS["neutral"])
    app.dashboard_detail_indicator.pack(pady=5)
    nav = ctk.CTkFrame(right, fg_color="transparent"); nav.pack(fill="x", padx=6, pady=4)
    for text, command in (("Tag Manager",lambda: app.tabs.set("Tag Manager")),("Digital",lambda: app.tabs.set("Entradas Digitais")),("Analog",lambda: app.tabs.set("Entradas Analógicas"))):
        ctk.CTkButton(nav, text=text, width=100, command=command).pack(side="left", padx=2)

    lower = ctk.CTkFrame(root, fg_color="transparent"); lower.pack(fill="x", pady=(6,0))
    app.dashboard_panel_labels = {}
    panels = ("Communication", "Alarms", "Trends", "Simulation / Project")
    for column, title in enumerate(panels):
        panel = ctk.CTkFrame(lower, fg_color=CARD_BG, border_width=1, border_color=BORDER)
        panel.grid(row=0, column=column, padx=3, sticky="nsew"); lower.grid_columnconfigure(column, weight=1)
        ctk.CTkLabel(panel, text=title, font=("Arial", 11, "bold"), text_color=COLORS["cyan"]).pack(pady=(5,1))
        label = ctk.CTkLabel(panel, text="—", justify="left", font=("Arial", 10)); label.pack(padx=6, pady=2)
        app.dashboard_panel_labels[title] = label
        button_row=ctk.CTkFrame(panel,fg_color="transparent");button_row.pack(pady=(1,5))
        actions={
            "Communication":(("Tags",lambda:app.tabs.set("Tag Manager")),),
            "Alarms":(("Open",lambda:app.tabs.set("Alarmes")),),
            "Trends":(("Open",lambda:app.tabs.set("Trends")),("Start",lambda:_trend_action(app,True)),("Stop",lambda:_trend_action(app,False))),
            "Simulation / Project":(("Digital",lambda:app.tabs.set("Entradas Digitais")),("Analog",lambda:app.tabs.set("Entradas Analógicas")),("Stop all",lambda:stop_all_simulations(app)),("Save",app.save_project),("Save as",app.save_project_as),("Folder",lambda:open_project_folder(app))),
        }[title]
        for text,command in actions:ctk.CTkButton(button_row,text=text,width=58,height=24,command=command).pack(side="left",padx=1)

    event_frame = ctk.CTkFrame(root, fg_color=CARD_BG, border_width=1, border_color=BORDER)
    event_frame.pack(fill="x", pady=(6,0))
    app.dashboard_event_table = ttk.Treeview(event_frame, columns=("time","severity","event","detail"), show="headings", height=4)
    for col, width in (("time",80),("severity",80),("event",180),("detail",600)):
        app.dashboard_event_table.heading(col,text=col.title()); app.dashboard_event_table.column(col,width=width,anchor="w")
    app.dashboard_event_table.pack(fill="x", padx=5, pady=5)
    record_dashboard_event(app, "Dashboard ready")
    update_dashboard(app)
    _schedule_dashboard(app)


def _schedule_dashboard(app):
    if getattr(app, "is_closing", False) or getattr(app, "_shutdown_started", False): return
    job = None
    def run():
        app._dashboard_after_jobs.discard(job)
        if getattr(app, "is_closing", False): return
        update_dashboard(app); _schedule_dashboard(app)
    job = app.schedule_job(DASHBOARD_REFRESH_MS, run)
    if job is not None: app._dashboard_after_jobs.add(job)


def cancel_dashboard_callbacks(app):
    for job in tuple(getattr(app, "_dashboard_after_jobs", ())):
        try: app.cancel_job(job)
        except Exception: pass
    getattr(app, "_dashboard_after_jobs", set()).clear()


def clear_dashboard_search(app):
    app.dashboard_search_entry.delete(0,"end"); refresh_dashboard_table(app)


def sort_dashboard(app, column):
    if app._dashboard_sort_column == column: app._dashboard_sort_descending = not app._dashboard_sort_descending
    else: app._dashboard_sort_column, app._dashboard_sort_descending = column, False
    refresh_dashboard_table(app)


def _source(runtime, brand):
    if runtime is None or runtime.source is None: return "Unknown"
    source = str(getattr(runtime.source, "value", runtime.source))
    return "Internal Simulator" if brand == "Simulator" and source == "PLC" else source.title()


def refresh_dashboard_table(app):
    tags = get_dashboard_tags(app)
    query = app.dashboard_search_entry.get() if hasattr(app,"dashboard_search_entry") else ""
    quick = app.dashboard_filter_menu.get() if hasattr(app,"dashboard_filter_menu") else "All"
    tags = filter_dashboard_tags(tags, query, quick, app.tag_runtime)
    if quick == "Alarm active":
        active = {a.get("source") for a in getattr(app,"alarms",[]) if a.get("active")}
        tags = [tag for tag in tags if tag.name in active]
    values = {tag.name: app.tag_runtime.get_value(tag.name) for tag in tags}
    alarm_names = {a.get("source") for a in getattr(app,"alarms",[]) if a.get("active")}
    brand=connection_brand(app)
    def key(tag):
        runtime=app.tag_runtime.get(tag.name)
        mapping={"status":bool(runtime and runtime.valid),"name":tag.name.casefold(),"address":tag.address.casefold(),"type":tag.data_type,"value":values[tag.name] if values[tag.name] is not None else float("-inf"),"source":_source(runtime,brand),"alarm":tag.name in alarm_names,"trend":tag.enabled_trend}
        return mapping.get(app._dashboard_sort_column,tag.name.casefold())
    tags=sorted(tags,key=key,reverse=app._dashboard_sort_descending)
    signature=(app.dashboard_search_entry.get(),app.dashboard_filter_menu.get(),app._dashboard_sort_column,app._dashboard_sort_descending,tuple((tag.name,values[tag.name],_source(app.tag_runtime.get(tag.name),brand),tag.name in alarm_names,tag.enabled_trend) for tag in tags))
    if signature == getattr(app,"_dashboard_table_signature",None):
        refresh_dashboard_detail(app); return
    app._dashboard_table_signature=signature
    selected = app._dashboard_selected_name
    table = app.dashboard_tag_table; table.delete(*table.get_children()); app._dashboard_visible_tags = tags
    selected_item = None
    for index, tag in enumerate(tags):
        runtime = app.tag_runtime.get(tag.name); valid = bool(runtime and runtime.valid); value = runtime.value if valid else "—"
        item = table.insert("","end",iid=str(index),values=("● GOOD" if valid else "● BAD",tag.name,tag.address,tag.data_type,value,_source(runtime,brand),"ACTIVE" if tag.name in alarm_names else "Normal","ON" if tag.enabled_trend else "Off"))
        if tag.name == selected: selected_item = item
    if selected_item is None and tags: selected_item = "0"
    if selected_item is not None: table.selection_set(selected_item); app._dashboard_selected_name = tags[int(selected_item)].name
    app.dashboard_count_label.configure(text=f"{len(tags)} of {len(get_dashboard_tags(app))} dashboard tags" if tags else "No dashboard-enabled tags")
    refresh_dashboard_detail(app)


def refresh_dashboard_detail(app):
    selection = app.dashboard_tag_table.selection()
    if not selection: return
    index = app.dashboard_tag_table.index(selection[0])
    if index >= len(app._dashboard_visible_tags): return
    tag = app._dashboard_visible_tags[index]; app._dashboard_selected_name = tag.name
    runtime = app.tag_runtime.get(tag.name); valid = bool(runtime and runtime.valid); effective = runtime.value if valid else "—"
    plc = getattr(app,"_plc_values",{}).get(tag.name,"—"); simulated = getattr(app,"_simulated_values",{}).get(tag.name,"—")
    source = _source(runtime, connection_brand(app)); updated = time.strftime("%H:%M:%S",time.localtime(runtime.updated_at)) if valid and runtime.updated_at else "Never"
    content = {"Name":tag.name,"Address":tag.address,"Type / Direction":f"{tag.data_type} / {tag.direction}","Effective value":effective,"PLC value":plc,"Simulated value":simulated,"Source / Quality":f"{source} / {'GOOD' if valid else 'BAD'}","Features":f"Sim {tag.enabled_sim} · Trend {tag.enabled_trend} · Alarm {tag.enabled_alarm} · Dashboard {tag.enabled_dashboard}","Last update":updated}
    for field,value in content.items(): app.dashboard_detail_labels[field].configure(text=f"{field}: {value}")
    if tag.data_type == "BOOL" and valid: app.dashboard_detail_indicator.configure(text="● ON" if bool(effective) else "● OFF",text_color=COLORS["green"] if bool(effective) else COLORS["red"])
    else: app.dashboard_detail_indicator.configure(text=str(effective),text_color=COLORS["cyan"] if valid else COLORS["neutral"])


def open_selected_dashboard_tag(app):
    name = getattr(app,"_dashboard_selected_name",None)
    tag = next((t for t in getattr(app,"tags",[]) if t.name == name),None)
    if tag is None: return
    if tag.data_type == "BOOL":
        from ui.digital_tab import refresh_digital_tab
        app._digital_selected_tag_name=name; app.tabs.set("Entradas Digitais"); refresh_digital_tab(app)
    else:
        from ui.analog_tab import refresh_analog_tab
        app._analog_selected_tag_name=name; app.tabs.set("Entradas Analógicas"); refresh_analog_tab(app)


def update_dashboard(app, last_message=None):
    if not hasattr(app,"dashboard_cards"): return
    if last_message: record_dashboard_event(app,last_message)
    values=dashboard_summary_values(app); connected=app.plc_service.is_connected(); brand=connection_brand(app); diagnostics=app.plc_service.diagnostics_snapshot(); project=os.path.basename(getattr(app,"project_path","") or "No project")
    for title,(value,color) in values.items(): app.dashboard_cards[title].configure(text=str(value),text_color=COLORS[color])
    refresh_dashboard_table(app)
    alarm=dashboard_alarm_summary(app); trend_data=getattr(app,"trend_data",{"time":[],"tags":{}}); selected_trends=len(getattr(app,"trend_visible_tags",set())) if hasattr(app,"trend_visible_tags") else sum(v.get() for v in getattr(app,"trend_tag_vars",{}).values()) if hasattr(app,"trend_tag_vars") else 0
    app.dashboard_panel_labels["Communication"].configure(text=f"Driver: {diagnostics['brand'] or 'None'} · {'Connected' if connected else 'Disconnected'}\nReads: {diagnostics['read_success_count']} ok / {diagnostics['read_error_count']} err · avg {diagnostics['average_read_duration_ms']:.1f} ms · {_fmt_time(diagnostics['last_read_timestamp'])}\nWrites: {diagnostics['write_success_count']} ok / {diagnostics['write_error_count']} err · avg {diagnostics['average_write_duration_ms']:.1f} ms · {_fmt_time(diagnostics['last_write_timestamp'])}\nReconnects: {diagnostics['reconnect_count']}")
    app.dashboard_panel_labels["Alarms"].configure(text=f"Active: {alarm['active']} · Unack: {alarm['unacknowledged']} · High priority: {alarm['high_priority']}\nLatest: {alarm['latest'].get('source') if alarm['latest'] else 'None'} · Cleared: {alarm['latest_cleared'] or 'None'}")
    trend_times=trend_data.get('time',[]); latest_sample=_fmt_time(getattr(app,'trend_start_time',0)+(trend_times[-1] if trend_times else 0)) if trend_times else "Never"
    app.dashboard_panel_labels["Trends"].configure(text=f"{'ON' if getattr(app,'trend_running',False) else 'OFF'} · Selected: {selected_trends}\nBuffered points: {len(trend_times)} · Duration: {trend_times[-1] if trend_times else 0}s · Latest: {latest_sample}")
    active_profiles=sum(bool(v) for v in getattr(app,"analog_profile_running",{}).values()); pulses=len(getattr(app,"pending_pulse_callbacks",{})); active_digital=sum(1 for tag in getattr(app,"tags",[]) if tag.data_type=="BOOL" and tag.name in getattr(app,"_simulated_values",{})); dirty="DIRTY" if getattr(app,"_project_dirty",False) else "CLEAN"
    connection=_connection_summary(app,brand); saved=_fmt_time(getattr(app,"_last_project_save_timestamp",None)); path=getattr(app,"project_path",None) or "No project file"
    app.dashboard_panel_labels["Simulation / Project"].configure(text=f"Digital active: {active_digital} · Pulses: {pulses} · Analog profiles: {active_profiles} · Internal: {'connected' if brand=='Simulator' and connected else 'off'}\n{project} · {dirty} · v{APP_VERSION}\n{connection} · Saved: {saved}\n{path}")


def refresh_dashboard(app): update_dashboard(app)


def _fmt_time(timestamp): return time.strftime("%H:%M:%S",time.localtime(timestamp)) if timestamp else "Never"


def _connection_summary(app,brand):
    if brand=="Simulator":return "Internal Simulator"
    if brand=="Siemens":
        return f"{connection_value(app,'ip')} · Rack {connection_value(app,'rack')} Slot {connection_value(app,'slot')} DB {connection_value(app,'db_number')}"
    return f"{connection_value(app,'ip')} · {brand}"


def record_dashboard_event(app, message, severity="INFO", detail=""):
    message=str(message).strip()
    if not message:return
    if not hasattr(app,"dashboard_events"): app.dashboard_events=deque(maxlen=EVENT_LIMIT)
    if not isinstance(app.dashboard_events,deque): app.dashboard_events=deque(app.dashboard_events,maxlen=EVENT_LIMIT)
    lower=message.casefold()
    if any(word in lower for word in ("error","erro","failed","alarm active")): severity="ERROR"
    elif any(word in lower for word in ("warning","degraded")): severity="WARN"
    app.dashboard_events.append((_fmt_time(time.time()),severity,message,detail))
    render_dashboard_events(app)


def clear_dashboard_events(app): app.dashboard_events=deque(maxlen=EVENT_LIMIT); render_dashboard_events(app)


def render_dashboard_events(app):
    table=getattr(app,"dashboard_event_table",None)
    if table is None:return
    table.delete(*table.get_children())
    for event in list(app.dashboard_events)[-20:]:
        if len(event)==2:event=(event[0],"INFO",event[1],"")
        table.insert("","end",values=event)


def stop_all_simulations(app):
    if not messagebox.askyesno("Stop simulations","Stop all pulses and analog profiles?"):return
    for job in tuple(getattr(app,"pending_pulse_callbacks",{}).values()): app.cancel_job(job)
    getattr(app,"pending_pulse_callbacks",{}).clear()
    manager=getattr(app,"analog_simulation_manager",None)
    if manager is not None: manager.stop_all()
    else:
        for index in tuple(getattr(app,"analog_profile_running",{})): app.analog_profile_running[index]=False
    record_dashboard_event(app,"All simulations stopped","WARN")


def _trend_action(app, start):
    app.ensure_trend_tab()
    from ui.trend_tab import start_trend, stop_trend
    (start_trend if start else stop_trend)(app)


def open_project_folder(app):
    path=os.path.dirname(getattr(app,"project_path","") or "")
    if path and os.path.isdir(path): subprocess.Popen(["xdg-open",path],start_new_session=True)
