import csv
import customtkinter as ctk
from io import StringIO
import logging
from pathlib import Path
import re
import shutil
import sys
from tkinter import filedialog, messagebox, ttk

from core.tag_model import Tag
from ui.header import connection_brand
from ui.table_utils import clear_entry, debounce


LOGGER = logging.getLogger(__name__)
CSV_FORMAT_ERROR = "CSV format invalid. Check required columns."
CSV_READ_ERROR = "Unable to read CSV file. Check file path and permissions."
CSV_ENCODING_ERROR = (
    "Unable to read CSV encoding. Save the file as UTF-8 CSV and try again."
)
CSV_EXPORT_ERROR = "Unable to export CSV. Check file path and permissions."
CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


class CSVEncodingError(ValueError):
    """Raised when a CSV cannot be decoded with a supported encoding."""


def _open_csv_text(file_path):
    data = Path(file_path).read_bytes()
    for encoding in CSV_ENCODINGS:
        try:
            text = data.decode(encoding)
            LOGGER.info("CSV import stage: file decoded encoding=%s bytes=%d", encoding, len(data))
            return StringIO(text, newline="")
        except UnicodeDecodeError:
            continue
    raise CSVEncodingError(CSV_ENCODING_ERROR)


COL_WIDTHS = {
    "name": 180,
    "type": 90,
    "direction": 120,
    "address": 140,
    "sim": 70,
    "trend": 70,
    "alarm": 70,
    "dash": 70,
    "delete": 90,
}

TAG_TABLE_STYLE = "TagManager.Treeview"
TAG_SCROLLBAR_STYLE = "TagManager.Vertical.TScrollbar"

TAG_CSV_FIELDS = [
    "name",
    "data_type",
    "direction",
    "address",
    "enabled_sim",
    "enabled_trend",
    "enabled_alarm",
    "enabled_dashboard",
]

TRUE_CSV_VALUES = {"1", "true", "yes", "on"}
FALSE_CSV_VALUES = {"", "0", "false", "no", "off"}

TEMPLATE_FILENAMES = {
    "Siemens": "siemens_tags_template.csv",
    "Schneider": "schneider_tags_template.csv",
    "Rockwell": "rockwell_tags_template.csv",
    "Omron": "omron_tags_template.csv",
    "Modbus TCP": "modbus_tcp_tags_template.csv",
    "Simulator": "universal_tags_template.csv",
}


def create_tag_manager_tab(app):
    if not hasattr(app, "tags"):
        app.tags = []

    frame = ctk.CTkFrame(app.tab_tags)
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    controls = ctk.CTkFrame(frame)
    controls.pack(fill="x", padx=10, pady=10)

    app.tag_name_entry = ctk.CTkEntry(controls, width=180)
    app.tag_name_entry.insert(0, "Start_Button")
    app.tag_name_entry.pack(side="left", padx=5)
    app.tag_name_entry.bind(
        "<KeyRelease>",
        lambda _event: on_tag_name_edited(app),
    )

    app.tag_type_menu = ctk.CTkOptionMenu(
        controls,
        values=["BOOL", "INT", "REAL"],
        command=lambda _value: update_tag_address_context(app),
        width=90
    )
    app.tag_type_menu.set("BOOL")
    app.tag_type_menu.pack(side="left", padx=5)

    app.tag_direction_menu = ctk.CTkOptionMenu(
        controls,
        values=["Input", "Feedback", "Output", "Internal"],
        command=lambda _value: update_tag_address_context(app),
        width=120
    )
    app.tag_direction_menu.set("Input")
    app.tag_direction_menu.pack(side="left", padx=5)

    app.tag_address_entry = ctk.CTkEntry(controls, width=140)
    app.tag_address_entry.insert(0, "DBX0.0")
    app.tag_address_entry.pack(side="left", padx=5)
    app.tag_address_manual_edit = False
    app.tag_last_suggested_address = "DBX0.0"
    app.tag_address_entry.bind(
        "<KeyRelease>",
        lambda _event: on_tag_address_edited(app),
    )
    app.tag_address_entry.bind(
        "<FocusOut>",
        lambda _event: on_tag_address_edited(app),
    )

    app.tag_suggest_button = ctk.CTkButton(
        controls,
        text="Suggest Address",
        command=lambda: suggest_tag_address(app),
        width=125,
    )
    app.tag_suggest_button.pack(side="left", padx=5)

    ctk.CTkButton(
        controls,
        text="Adicionar Tag",
        command=lambda: add_tag(app),
        width=130
    ).pack(side="left", padx=10)

    app.tag_update_signals_button = ctk.CTkButton(
        controls,
        text="Atualizar Sinais",
        command=lambda: app.generate_signals(),
        width=130
    )
    app.tag_update_signals_button.pack(side="left", padx=5)

    app.tag_import_csv_button = ctk.CTkButton(
        controls,
        text="Import CSV",
        command=lambda: import_tags_csv(app),
        width=110,
    )
    app.tag_import_csv_button.pack(side="left", padx=5)

    app.tag_import_tia_csv_button = ctk.CTkButton(
        controls,
        text="Import TIA CSV",
        command=lambda: import_tia_csv(app),
        width=120,
    )
    app.tag_import_tia_csv_button.pack(side="left", padx=5)

    app.tag_import_schneider_csv_button = ctk.CTkButton(
        controls,
        text="Import Schneider CSV",
        command=lambda: import_schneider_csv(app),
        width=155,
    )
    app.tag_import_schneider_csv_button.pack(side="left", padx=5)

    app.tag_export_csv_button = ctk.CTkButton(
        controls,
        text="Export CSV",
        command=lambda: export_tags_csv(app),
        width=110,
    )
    app.tag_export_csv_button.pack(side="left", padx=5)

    app.tag_export_template_csv_button = ctk.CTkButton(
        controls,
        text="Exportar Template CSV",
        command=lambda: export_csv_template(app),
        width=165,
    )
    app.tag_export_template_csv_button.pack(side="left", padx=5)

    update_csv_button_visibility(app)

    app.tag_validation_label = ctk.CTkLabel(
        frame,
        text="",
        text_color="gray",
        anchor="w",
    )
    app.tag_validation_label.pack(fill="x", padx=15, pady=(0, 5))

    app.tag_database_validation_label = ctk.CTkLabel(
        frame,
        text="",
        text_color="gray",
        anchor="w",
    )
    app.tag_database_validation_label.pack(fill="x", padx=15, pady=(0, 5))

    search_row = ctk.CTkFrame(frame, fg_color="transparent")
    search_row.pack(fill="x", padx=8, pady=(2, 4))
    ctk.CTkLabel(search_row, text="Search:").pack(side="left", padx=(4, 6))
    app.tag_search_entry = ctk.CTkEntry(
        search_row, width=320,
        placeholder_text="Name, address, type or direction",
    )
    app.tag_search_entry.pack(side="left", padx=(0, 4))
    app.tag_search_clear_button = ctk.CTkButton(
        search_row, text="×", width=32,
        command=lambda: clear_tag_search(app),
    )
    app.tag_search_clear_button.pack(side="left", padx=(0, 10))
    app.tag_search_count_label = ctk.CTkLabel(search_row, text="0 tags")
    app.tag_search_count_label.pack(side="left", padx=6)
    app.tag_search_entry.bind(
        "<KeyRelease>", lambda event: on_tag_search_key(app, event),
    )
    app.tag_search_entry.bind(
        "<Return>", lambda _event: select_first_filtered_tag(app),
    )
    app.app.bind(
        "<Control-f>", lambda _event: focus_tag_search(app), add="+",
    )

    configure_tag_table_style(frame)
    table_frame = ctk.CTkFrame(
        frame, fg_color="#242424", border_width=1, border_color="#454545",
    )
    table_frame.pack(fill="both", expand=True, padx=6, pady=(3, 6))
    columns = (
        "name", "data_type", "direction", "address", "enabled_sim",
        "enabled_trend", "enabled_alarm", "enabled_dashboard", "delete",
    )
    headings = (
        "Nome", "Tipo", "Direção", "Endereço", "Sim", "Trend",
        "Alarme", "Dash", "Ação",
    )
    control_row = ttk.Frame(table_frame, style="TagManager.Controls.TFrame")
    control_row.pack(fill="x")
    widths = tuple(COL_WIDTHS.values())
    for index, width in enumerate(widths):
        control_row.grid_columnconfigure(
            index, minsize=width, weight=1 if index == 0 else 0,
        )
    # Reserve the same space used by the vertical scrollbar below.
    control_row.grid_columnconfigure(len(columns), minsize=16, weight=0)
    app.tag_master_checkboxes = {}
    for column, option in (
        (4, "enabled_sim"),
        (5, "enabled_trend"),
        (6, "enabled_alarm"),
        (7, "enabled_dashboard"),
    ):
        checkbox = ttk.Checkbutton(
            control_row,
            text="Todos",
            style="TagManager.TCheckbutton",
            command=lambda field=option: on_master_tag_option_clicked(app, field),
        )
        checkbox.grid(row=0, column=column, padx=2, pady=2)
        app.tag_master_checkboxes[option] = checkbox

    tree_body = ttk.Frame(table_frame, style="TagManager.Controls.TFrame")
    tree_body.pack(fill="both", expand=True)
    app.tag_table = ttk.Treeview(
        tree_body, columns=columns, show="headings", selectmode="browse",
        style=TAG_TABLE_STYLE,
    )
    for column, heading, width in zip(columns, headings, COL_WIDTHS.values()):
        app.tag_table.heading(column, text=heading)
        app.tag_table.column(
            column, width=width, minwidth=width,
            stretch=column == "name",
            anchor="w" if column == "name" else "center",
        )
    scrollbar = ttk.Scrollbar(
        tree_body, orient="vertical", command=app.tag_table.yview,
        style=TAG_SCROLLBAR_STYLE,
    )
    app.tag_table.pack(side="left", fill="both", expand=True)
    app.tag_table.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    app.tag_table.bind(
        "<ButtonRelease-1>", lambda event: on_tag_table_click(app, event),
    )

    refresh_tag_table(app)
    update_tag_address_context(app)


def filter_tag_collection(tags, query):
    """Return a separate filtered view; never mutate the source collection."""
    query = str(query or "").strip().casefold()
    if not query:
        return list(tags)
    return [
        tag for tag in tags
        if query in tag.name.casefold()
        or query in tag.address.casefold()
        or query in tag.data_type.casefold()
        or query in tag.direction.casefold()
    ]


def on_tag_search_key(app, event):
    if getattr(event, "keysym", "") == "Escape":
        clear_tag_search(app)
        return "break"
    debounce(
        app, "tag_search", 150,
        lambda: refresh_tag_table(app, view_only=True),
    )


def clear_tag_search(app):
    clear_entry(app.tag_search_entry)
    refresh_tag_table(app, view_only=True)
    app.tag_search_entry.focus_set()


def focus_tag_search(app):
    app.tag_search_entry.focus_set()
    app.tag_search_entry.select_range(0, "end")
    return "break"


def select_first_filtered_tag(app):
    children = app.tag_table.get_children()
    if children:
        app.tag_table.selection_set(children[0])
        app.tag_table.focus(children[0])
        app.tag_table.see(children[0])
    return "break"


def configure_tag_table_style(widget):
    """Create the dark native table styles without changing the global theme."""
    style = ttk.Style(widget)
    style.configure(
        TAG_TABLE_STYLE,
        background="#242424",
        fieldbackground="#242424",
        foreground="#f0f0f0",
        bordercolor="#454545",
        lightcolor="#454545",
        darkcolor="#454545",
        borderwidth=1,
        relief="flat",
        rowheight=28,
        font=("Arial", 11),
    )
    style.configure(
        f"{TAG_TABLE_STYLE}.Heading",
        background="#343434",
        foreground="#f0f0f0",
        bordercolor="#454545",
        lightcolor="#454545",
        darkcolor="#454545",
        relief="flat",
        padding=(5, 6),
        font=("Arial", 11, "bold"),
    )
    style.map(
        TAG_TABLE_STYLE,
        background=[("selected", "#1f6aa5")],
        foreground=[("selected", "#ffffff")],
    )
    style.map(
        f"{TAG_TABLE_STYLE}.Heading",
        background=[("active", "#3d3d3d")],
        relief=[("pressed", "flat"), ("active", "flat")],
    )
    style.configure(
        TAG_SCROLLBAR_STYLE,
        background="#343434",
        troughcolor="#242424",
        bordercolor="#454545",
        arrowcolor="#f0f0f0",
        lightcolor="#343434",
        darkcolor="#343434",
        relief="flat",
        borderwidth=1,
    )
    style.map(
        TAG_SCROLLBAR_STYLE,
        background=[("active", "#454545"), ("pressed", "#1f6aa5")],
    )
    style.configure("TagManager.Controls.TFrame", background="#2b2b2b")
    style.configure(
        "TagManager.TCheckbutton",
        background="#2b2b2b",
        foreground="#f0f0f0",
        font=("Arial", 10),
        padding=(2, 2),
    )
    style.map(
        "TagManager.TCheckbutton",
        background=[("active", "#343434")],
        foreground=[("disabled", "#8a8a8a")],
    )


def update_csv_button_visibility(app):
    """Show only the CSV vendor importer for the selected PLC brand."""
    brand = connection_brand(app)
    vendor_buttons = (
        (app.tag_import_tia_csv_button, brand == "Siemens"),
        (app.tag_import_schneider_csv_button, brand == "Schneider"),
    )

    for button, visible in vendor_buttons:
        button.pack_forget()
        if visible:
            button.pack(
                side="left",
                padx=5,
                before=app.tag_export_csv_button,
            )


def create_header_cell(parent, text, column, width):
    ctk.CTkLabel(
        parent,
        text=text,
        font=("Arial", 13, "bold"),
        width=width,
        anchor="center"
    ).grid(row=0, column=column, padx=4, pady=6)


def add_tag(app):
    name = app.tag_name_entry.get().strip()
    if not name:
        app.tag_validation_label.configure(
            text="Nome da tag não pode estar vazio",
            text_color="red",
        )
        return

    if any(
        tag.name.strip().casefold() == name.casefold()
        for tag in app.tags
    ):
        app.tag_validation_label.configure(
            text=f"Nome de tag duplicado: {name}",
            text_color="red",
        )
        return

    data_type = app.tag_type_menu.get()
    address = resolve_tag_address(
        connection_brand(app),
        name,
        app.tag_address_entry.get(),
    )
    valid, validation_message = validate_tag_address(
        connection_brand(app),
        data_type,
        address,
    )
    if not valid:
        app.tag_validation_label.configure(
            text=validation_message,
            text_color="red",
        )
        return

    tag = Tag(
        name=name,
        data_type=data_type,
        direction=app.tag_direction_menu.get(),
        address=address,
        enabled_sim=True if app.tag_direction_menu.get() == "Input" else False,
        enabled_trend=True,
        enabled_alarm=False,
        enabled_dashboard=True
    )

    app.tags.append(tag)
    mark_project_modified(app)
    refresh_tag_table(app)
    app.tag_address_manual_edit = False
    app.generate_signals()


def normalize_and_validate_tag_names(tags):
    seen = set()
    for index, tag in enumerate(tags, start=1):
        name = str(tag.name or "").strip()
        if not name:
            return False, f"Tag {index}: nome vazio"

        identity = name.casefold()
        if identity in seen:
            return False, f"Nome de tag duplicado: {name}"

        tag.name = name
        seen.add(identity)

    return True, ""


def validate_tag_address(brand, data_type, address):
    brand = str(brand).strip()
    data_type = str(data_type).strip().upper()
    address = str(address).strip().upper()

    if brand == "Siemens":
        patterns = {
            "BOOL": (r"DBX\d+\.[0-7]", "BOOL Siemens requer DBX byte.bit (ex.: DBX0.0)"),
            "INT": (r"DBW\d+", "INT Siemens requer DBW byte (ex.: DBW0)"),
            "REAL": (r"DBD\d+", "REAL Siemens requer DBD byte (ex.: DBD0)"),
        }
    elif brand == "Schneider":
        patterns = {
            "BOOL": (r"%M\d+", "BOOL Schneider requer %M index (ex.: %M0)"),
            "INT": (r"%MW\d+", "INT Schneider requer %MW index (ex.: %MW0)"),
            "REAL": (r"%MW\d+", "REAL Schneider requer %MW index e ocupa 2 registos"),
        }
    elif brand == "Modbus TCP":
        patterns = {
            "BOOL": (
                r"(?:%?M)?\d+",
                "BOOL Modbus TCP requer %M0, M0 ou 0",
            ),
            "INT": (
                r"(?:%?MW)?\d+",
                "INT Modbus TCP requer %MW0, MW0 ou 0",
            ),
            "REAL": (
                r"(?:%?MW)?\d+",
                "REAL Modbus TCP requer %MW0, MW0 ou 0 e ocupa 2 registos",
            ),
        }
    elif brand == "Rockwell":
        patterns = {
            data_type: (
                r"[A-Z_][A-Z0-9_]*",
                "Rockwell requer um nome de tag simbólico (ex.: Start_Button)",
            )
            for data_type in ("BOOL", "INT", "REAL")
        }
    elif brand == "Omron":
        patterns = {
            "BOOL": (
                r"CIO\d+\.(?:0\d|1[0-5])",
                "BOOL Omron requer CIO word.bit (ex.: CIO100.05)",
            ),
            "INT": (r"D\d+", "INT Omron requer palavra DM (ex.: D100)"),
            "REAL": (
                r"D\d+",
                "REAL Omron requer palavra DM e ocupa 2 palavras",
            ),
        }
    elif brand == "Simulator":
        patterns = {
            data_type: (
                r".+",
                "Simulator requer apenas um endereço interno não vazio",
            )
            for data_type in ("BOOL", "INT", "REAL")
        }
    else:
        return False, f"Marca PLC não suportada: {brand}"

    rule = patterns.get(data_type)
    if rule is None:
        return False, f"Tipo de dados não suportado: {data_type}"

    pattern, error_message = rule
    if re.fullmatch(pattern, address) is None:
        return False, error_message

    if brand in ("Schneider", "Modbus TCP") and data_type == "REAL":
        return True, "Endereço válido; REAL ocupa 2 registos %MW"
    return True, "Endereço válido"


def suggest_tag_address(app):
    address = suggest_address(
        connection_brand(app),
        app.tag_type_menu.get(),
        app.tags,
        app.tag_name_entry.get(),
    )
    app.tag_address_entry.delete(0, "end")
    app.tag_address_entry.insert(0, address)
    app.tag_address_manual_edit = False
    app.tag_last_suggested_address = address

    _, message = validate_tag_address(
        connection_brand(app),
        app.tag_type_menu.get(),
        address,
    )
    app.tag_validation_label.configure(
        text=f"Sugestão: {address} — {message}",
        text_color="cyan",
    )


def resolve_tag_address(brand, tag_name, entered_address):
    """Resolve the stored PLC address without changing non-Rockwell rules."""
    if str(brand).strip() == "Rockwell":
        return str(tag_name).strip()
    if str(brand).strip() == "Simulator":
        return str(entered_address).strip()
    return str(entered_address).strip().upper()


def _sync_rockwell_tag_address(app):
    address = resolve_tag_address(
        "Rockwell",
        app.tag_name_entry.get(),
        app.tag_address_entry.get(),
    )
    app.tag_address_entry.delete(0, "end")
    app.tag_address_entry.insert(0, address)
    app.tag_address_manual_edit = False
    app.tag_last_suggested_address = address


def on_tag_name_edited(app):
    if connection_brand(app) != "Rockwell":
        return
    _sync_rockwell_tag_address(app)
    validate_current_tag_address(app)


def on_tag_address_edited(app):
    address = app.tag_address_entry.get().strip()
    last_suggestion = getattr(app, "tag_last_suggested_address", "")
    app.tag_address_manual_edit = (
        bool(address)
        and address.upper() != last_suggestion.upper()
    )
    validate_current_tag_address(app)


def validate_current_tag_address(app):
    address = app.tag_address_entry.get().strip()
    if not address:
        app.tag_validation_label.configure(
            text="Endereço vazio — use Suggest Address ou introduza um endereço",
            text_color="orange",
        )
        return False

    valid, message = validate_tag_address(
        connection_brand(app),
        app.tag_type_menu.get(),
        address,
    )
    app.tag_validation_label.configure(
        text=message,
        text_color="lime" if valid else "red",
    )
    return valid


def update_tag_address_context(app):
    if not hasattr(app, "tag_address_entry"):
        return

    if connection_brand(app) == "Rockwell":
        if app.tag_address_entry.winfo_manager():
            app.tag_address_entry.pack_forget()
        _sync_rockwell_tag_address(app)
        validate_current_tag_address(app)
        return

    if not app.tag_address_entry.winfo_manager():
        app.tag_address_entry.pack(
            side="left",
            padx=5,
            before=app.tag_suggest_button,
        )

    address = app.tag_address_entry.get().strip()
    if not address or not getattr(app, "tag_address_manual_edit", False):
        suggest_tag_address(app)
    else:
        validate_current_tag_address(app)


def suggest_address(brand, data_type, tags, tag_name=None):
    brand = str(brand).strip()
    data_type = str(data_type).strip().upper()
    if data_type not in ["BOOL", "INT", "REAL"]:
        raise ValueError(f"Tipo de dados não suportado: {data_type}")

    if brand == "Siemens":
        occupied_bytes, occupied_bits = _siemens_occupancy(tags)

        if data_type == "BOOL":
            byte_index = 0
            while True:
                if byte_index not in occupied_bytes:
                    for bit_index in range(8):
                        if (byte_index, bit_index) not in occupied_bits:
                            return f"DBX{byte_index}.{bit_index}"
                byte_index += 1

        size = 2 if data_type == "INT" else 4
        prefix = "DBW" if data_type == "INT" else "DBD"
        candidate = 0
        while True:
            byte_range = range(candidate, candidate + size)
            if (
                not any(byte in occupied_bytes for byte in byte_range)
                and not any(byte == bit_byte for byte in byte_range for bit_byte, _ in occupied_bits)
            ):
                return f"{prefix}{candidate}"
            candidate += size

    if brand in ("Schneider", "Modbus TCP"):
        occupied_coils, occupied_registers = _modbus_occupancy(tags, brand)

        if data_type == "BOOL":
            candidate = 0
            while candidate in occupied_coils:
                candidate += 1
            return f"%M{candidate}"

        register_count = 2 if data_type == "REAL" else 1
        candidate = 0
        while any(
            register in occupied_registers
            for register in range(candidate, candidate + register_count)
        ):
            candidate += 1
        return f"%MW{candidate}"

    if brand == "Rockwell":
        return str(tag_name or "").strip()

    if brand == "Omron":
        occupied_bits, occupied_words = _omron_occupancy(tags)
        if data_type == "BOOL":
            candidate = 0
            while (candidate // 16, candidate % 16) in occupied_bits:
                candidate += 1
            return f"CIO{candidate // 16}.{candidate % 16:02d}"

        word_count = 2 if data_type == "REAL" else 1
        candidate = 0
        while any(
            word in occupied_words
            for word in range(candidate, candidate + word_count)
        ):
            candidate += 1
        return f"D{candidate}"

    if brand == "Simulator":
        suggestion = str(tag_name or "").strip()
        return suggestion or f"SIM_{data_type}"

    raise ValueError(f"Marca PLC não suportada: {brand}")


def _siemens_occupancy(tags):
    occupied_bytes = set()
    occupied_bits = set()

    for tag in tags:
        valid, _ = validate_tag_address("Siemens", tag.data_type, tag.address)
        if not valid:
            continue

        address = tag.address.strip().upper()
        if tag.data_type == "BOOL":
            byte_text, bit_text = address.removeprefix("DBX").split(".")
            occupied_bits.add((int(byte_text), int(bit_text)))
        else:
            prefix = "DBW" if tag.data_type == "INT" else "DBD"
            byte_index = int(address.removeprefix(prefix))
            size = 2 if tag.data_type == "INT" else 4
            occupied_bytes.update(range(byte_index, byte_index + size))

    return occupied_bytes, occupied_bits


def _schneider_occupancy(tags):
    return _modbus_occupancy(tags, "Schneider")


def _modbus_occupancy(tags, brand):
    occupied_coils = set()
    occupied_registers = set()

    for tag in tags:
        valid, _ = validate_tag_address(brand, tag.data_type, tag.address)
        if not valid:
            continue

        address = tag.address.strip().upper()
        index_match = re.search(r"\d+$", address)
        if index_match is None:
            continue
        index = int(index_match.group())
        if tag.data_type == "BOOL":
            occupied_coils.add(index)
        else:
            count = 2 if tag.data_type == "REAL" else 1
            occupied_registers.update(range(index, index + count))

    return occupied_coils, occupied_registers


def _omron_occupancy(tags):
    occupied_bits = set()
    occupied_words = set()
    for tag in tags:
        if not validate_tag_address("Omron", tag.data_type, tag.address)[0]:
            continue
        address = str(tag.address).strip().upper()
        if tag.data_type == "BOOL":
            word_text, bit_text = address.removeprefix("CIO").split(".")
            occupied_bits.add((int(word_text), int(bit_text)))
        else:
            word = int(address.removeprefix("D"))
            count = 2 if tag.data_type == "REAL" else 1
            occupied_words.update(range(word, word + count))
    return occupied_bits, occupied_words


def parse_csv_bool(value):
    normalized = str(value).strip().lower()
    if normalized in TRUE_CSV_VALUES:
        return True
    if normalized in FALSE_CSV_VALUES:
        return False
    raise ValueError(f"valor booleano inválido: {value}")


def _read_csv_dialect(file):
    sample = file.read(4096)
    file.seek(0)
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        return csv.excel


def _normalize_csv_header(header):
    return str(header or "").strip()


def _build_csv_header_map(fieldnames):
    header_map = {}
    detected_columns = []

    for header in fieldnames:
        normalized = _normalize_csv_header(header)
        if not normalized or normalized.lower().startswith("unnamed"):
            continue

        key = normalized.lower()
        detected_columns.append(normalized)
        header_map.setdefault(key, header)

    return header_map, detected_columns


def _format_missing_csv_columns_error(missing_fields, detected_columns):
    detected = ", ".join(detected_columns) if detected_columns else "(none)"
    return (
        "CSV format invalid. "
        "Missing columns: " + ", ".join(missing_fields) + ". "
        "Detected columns: " + detected + "."
    )


def _read_normalized_csv_rows(file):
    """Read the complete CSV and discard spreadsheet-only columns."""
    rows = list(csv.reader(file, dialect=_read_csv_dialect(file)))
    if not rows:
        raise ValueError("CSV sem cabeçalho")

    headers = [_normalize_csv_header(header) for header in rows[0]]
    kept_indexes = [
        index for index, header in enumerate(headers)
        if header and not header.lower().startswith("unnamed")
    ]
    normalized_headers = [headers[index] for index in kept_indexes]

    # csv.reader exposes surplus cells explicitly.  They have no header, so
    # treat them like trailing empty/Unnamed spreadsheet columns.
    normalized_rows = []
    for line_number, row in enumerate(rows[1:], start=2):
        padded_row = row + [""] * max(0, len(headers) - len(row))
        normalized_rows.append((
            line_number,
            [padded_row[index] for index in kept_indexes],
        ))

    return normalized_headers, normalized_rows


def read_tags_csv(file_path, brand=None):
    tags = []

    with _open_csv_text(file_path) as file:
        headers, rows = _read_normalized_csv_rows(file)
        header_map, detected_columns = _build_csv_header_map(headers)
        missing_fields = [
            field for field in TAG_CSV_FIELDS
            if field not in header_map
        ]
        if missing_fields:
            raise ValueError(_format_missing_csv_columns_error(
                missing_fields,
                detected_columns,
            ))
        if len(headers) != len(TAG_CSV_FIELDS):
            raise ValueError(
                "CSV format invalid. Normalized rows must contain exactly "
                f"{len(TAG_CSV_FIELDS)} required fields."
            )

        header_indexes = {
            field: headers.index(header_map[field]) for field in TAG_CSV_FIELDS
        }

        direction_names = {
            "input": "Input",
            "feedback": "Feedback",
            "output": "Output",
            "internal": "Internal",
        }

        for line_number, row in rows:
            if len(row) != len(TAG_CSV_FIELDS):
                raise ValueError(
                    f"linha {line_number}: expected exactly "
                    f"{len(TAG_CSV_FIELDS)} fields"
                )
            if not any(str(value or "").strip() for value in row):
                continue

            try:
                values = {
                    field: str(row[header_indexes[field]] or "").strip()
                    for field in TAG_CSV_FIELDS
                }

                data_type = values["data_type"].upper()
                if data_type not in ["BOOL", "INT", "REAL"]:
                    raise ValueError(
                        f"data_type inválido: {values['data_type']}"
                    )

                direction = direction_names.get(values["direction"].lower())
                if direction is None:
                    raise ValueError(
                        f"direction inválida: {values['direction']}"
                    )

                if not values["name"]:
                    raise ValueError("name vazio")

                address = values["address"]
                if brand not in ("Rockwell", "Simulator"):
                    address = address.upper()
                if brand is not None:
                    valid, validation_message = validate_tag_address(
                        brand,
                        data_type,
                        address,
                    )
                    if not valid:
                        raise ValueError(validation_message)

                tags.append(Tag(
                    name=values["name"],
                    data_type=data_type,
                    direction=direction,
                    address=address,
                    enabled_sim=parse_csv_bool(values["enabled_sim"]),
                    enabled_trend=parse_csv_bool(values["enabled_trend"]),
                    enabled_alarm=parse_csv_bool(values["enabled_alarm"]),
                    enabled_dashboard=parse_csv_bool(values["enabled_dashboard"]),
                ))
            except ValueError as error:
                raise ValueError(f"linha {line_number}: {error}") from error

    return tags


def write_tags_csv(file_path, tags):
    with open(file_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=TAG_CSV_FIELDS)
        writer.writeheader()

        for tag in tags:
            writer.writerow({
                "name": tag.name,
                "data_type": tag.data_type,
                "direction": tag.direction,
                "address": tag.address,
                "enabled_sim": "1" if tag.enabled_sim else "0",
                "enabled_trend": "1" if tag.enabled_trend else "0",
                "enabled_alarm": "1" if tag.enabled_alarm else "0",
                "enabled_dashboard": "1" if tag.enabled_dashboard else "0",
            })


def read_tia_tags_csv(file_path):
    tags = []

    with _open_csv_text(file_path) as file:
        sample = file.read(4096)
        file.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(file, dialect=dialect)
        if reader.fieldnames is None:
            raise ValueError("CSV TIA sem cabeçalho")

        header_map = {
            _normalize_import_header(header): header
            for header in reader.fieldnames
        }
        name_column = _find_import_column(header_map, ["name"])
        type_column = _find_import_column(
            header_map,
            ["data type", "datatype"],
        )
        logical_address_column = _find_import_column(
            header_map,
            ["logical address"],
        )
        address_column = _find_import_column(header_map, ["address"])

        missing = []
        if name_column is None:
            missing.append("Name")
        if type_column is None:
            missing.append("Data Type")
        if logical_address_column is None and address_column is None:
            missing.append("Logical Address/Address")
        if missing:
            raise ValueError("colunas TIA em falta: " + ", ".join(missing))

        type_map = {
            "bool": "BOOL",
            "boolean": "BOOL",
            "int": "INT",
            "real": "REAL",
        }

        for line_number, row in enumerate(reader, start=2):
            if not any(str(value or "").strip() for value in row.values()):
                continue

            try:
                name = str(row.get(name_column, "") or "").strip()
                tia_type = str(row.get(type_column, "") or "").strip()
                raw_address = ""
                if logical_address_column is not None:
                    raw_address = str(
                        row.get(logical_address_column, "") or ""
                    ).strip()
                if not raw_address and address_column is not None:
                    raw_address = str(
                        row.get(address_column, "") or ""
                    ).strip()

                if not name:
                    raise ValueError("Name vazio")

                data_type = type_map.get(tia_type.lower())
                if data_type is None:
                    raise ValueError(f"Data Type TIA não suportado: {tia_type}")

                address = raw_address.upper().removeprefix("%")
                valid, message = validate_tag_address(
                    "Siemens",
                    data_type,
                    address,
                )
                if not valid:
                    raise ValueError(message)

                tags.append(Tag(
                    name=name,
                    data_type=data_type,
                    direction="Input",
                    address=address,
                    enabled_sim=True,
                    enabled_trend=False,
                    enabled_alarm=False,
                    enabled_dashboard=True,
                ))
            except ValueError as error:
                raise ValueError(f"linha {line_number}: {error}") from error

    return tags


def _normalize_import_header(header):
    return re.sub(
        r"[\s_]+",
        " ",
        str(header or "").strip().lower(),
    )


def _find_import_column(header_map, candidates):
    for candidate in candidates:
        if candidate in header_map:
            return header_map[candidate]
    return None


def _find_import_columns(header_map, candidates):
    return [
        header_map[candidate]
        for candidate in candidates
        if candidate in header_map
    ]


def _first_import_value(row, columns):
    for column in columns:
        value = str(row.get(column, "") or "").strip()
        if value:
            return value
    return ""


# Compatibility for callers using the Phase 7B helper names.
_normalize_tia_header = _normalize_import_header
_find_tia_column = _find_import_column


def read_schneider_tags_csv(file_path):
    tags = []

    with _open_csv_text(file_path) as file:
        sample = file.read(4096)
        file.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(file, dialect=dialect)
        if reader.fieldnames is None:
            raise ValueError("CSV Schneider sem cabeçalho")

        header_map = {
            _normalize_import_header(header): header
            for header in reader.fieldnames
        }
        name_columns = _find_import_columns(
            header_map,
            ["name", "variable"],
        )
        type_columns = _find_import_columns(
            header_map,
            ["data type", "datatype", "type"],
        )
        address_column = _find_import_column(header_map, ["address"])

        missing = []
        if not name_columns:
            missing.append("Name/Variable")
        if not type_columns:
            missing.append("Type/Data Type")
        if address_column is None:
            missing.append("Address")
        if missing:
            raise ValueError(
                "colunas Schneider em falta: " + ", ".join(missing)
            )

        type_map = {
            "ebool": "BOOL",
            "bool": "BOOL",
            "int": "INT",
            "real": "REAL",
        }

        for line_number, row in enumerate(reader, start=2):
            if not any(str(value or "").strip() for value in row.values()):
                continue

            try:
                name = _first_import_value(row, name_columns)
                schneider_type = _first_import_value(row, type_columns)
                address = str(
                    row.get(address_column, "") or ""
                ).strip().upper()

                if not name:
                    raise ValueError("Name/Variable vazio")

                data_type = type_map.get(schneider_type.lower())
                if data_type is None:
                    raise ValueError(
                        "Type Schneider não suportado: "
                        f"{schneider_type}"
                    )

                valid, message = validate_tag_address(
                    "Schneider",
                    data_type,
                    address,
                )
                if not valid:
                    raise ValueError(message)

                tags.append(Tag(
                    name=name,
                    data_type=data_type,
                    direction="Input",
                    address=address,
                    enabled_sim=True,
                    enabled_trend=False,
                    enabled_alarm=False,
                    enabled_dashboard=True,
                ))
            except ValueError as error:
                raise ValueError(f"linha {line_number}: {error}") from error

    return tags


def import_tags_csv(app):
    file_path = filedialog.askopenfilename(
        initialdir="configs",
        filetypes=[("CSV files", "*.csv")],
    )
    if not file_path:
        return

    try:
        imported_tags = read_tags_csv(file_path, connection_brand(app))
    except (OSError, ValueError) as error:
        LOGGER.warning("Universal CSV import failed: %s", error)
        messagebox.showerror(
            "Erro Import CSV",
            CSV_READ_ERROR if isinstance(error, OSError) else str(error),
        )
        return

    apply_imported_tags(
        app,
        imported_tags,
        "Erro Import CSV",
        f"● {len(imported_tags)} TAGS IMPORTADAS",
    )


def import_tia_csv(app):
    file_path = filedialog.askopenfilename(
        initialdir="configs",
        filetypes=[("TIA CSV files", "*.csv"), ("All files", "*.*")],
    )
    if not file_path:
        return

    try:
        imported_tags = read_tia_tags_csv(file_path)
    except (OSError, ValueError) as error:
        LOGGER.warning("TIA CSV import failed: %s", error)
        messagebox.showerror(
            "Erro Import TIA CSV",
            CSV_READ_ERROR if isinstance(error, OSError) else (
                CSV_ENCODING_ERROR
                if isinstance(error, CSVEncodingError)
                else CSV_FORMAT_ERROR
            ),
        )
        return

    apply_imported_tags(
        app,
        imported_tags,
        "Erro Import TIA CSV",
        f"● {len(imported_tags)} TAGS TIA IMPORTADAS",
        target_brand="Siemens",
    )


def import_schneider_csv(app):
    file_path = filedialog.askopenfilename(
        initialdir="configs",
        filetypes=[
            ("Schneider CSV files", "*.csv"),
            ("All files", "*.*"),
        ],
    )
    if not file_path:
        return

    try:
        imported_tags = read_schneider_tags_csv(file_path)
    except (OSError, ValueError) as error:
        LOGGER.warning("Schneider CSV import failed: %s", error)
        messagebox.showerror(
            "Erro Import Schneider CSV",
            CSV_READ_ERROR if isinstance(error, OSError) else (
                CSV_ENCODING_ERROR
                if isinstance(error, CSVEncodingError)
                else CSV_FORMAT_ERROR
            ),
        )
        return

    apply_imported_tags(
        app,
        imported_tags,
        "Erro Import Schneider CSV",
        f"● {len(imported_tags)} TAGS SCHNEIDER IMPORTADAS",
        target_brand="Schneider",
    )


def apply_imported_tags(
    app,
    imported_tags,
    error_title,
    success_text,
    target_brand=None,
):
    if hasattr(app, "cancel_pending_tab_refreshes"):
        app.cancel_pending_tab_refreshes()
    if getattr(app, "is_rebuilding", False):
        LOGGER.info("CSV import superseded an active rebuild")
        app.is_rebuilding = False

    LOGGER.info("CSV import stage: rows parsed count=%d", len(imported_tags))
    names_valid, names_message = normalize_and_validate_tag_names(
        imported_tags
    )
    if not names_valid:
        LOGGER.warning("CSV import validation failed: %s", names_message)
        messagebox.showerror(error_title, CSV_FORMAT_ERROR)
        return False
    LOGGER.info("CSV import stage: rows validated count=%d", len(imported_tags))
    LOGGER.info("CSV import stage: tags staged count=%d", len(imported_tags))

    previous_tags = app.tags
    runtime_cache = getattr(app, "tag_runtime", None)
    runtime_snapshot = (
        runtime_cache.snapshot()
        if runtime_cache is not None and hasattr(runtime_cache, "snapshot")
        else None
    )
    previous_brand = None
    brand_changed = False
    if (
        target_brand is not None
        and hasattr(app, "brand_menu")
        and hasattr(app, "update_brand")
    ):
        previous_brand = connection_brand(app)
        brand_changed = previous_brand != target_brand

    def set_import_state(active):
        app.is_rebuilding = active
        for name in (
            "tag_import_csv_button", "tag_import_tia_csv_button",
            "tag_import_schneider_csv_button", "tag_update_signals_button",
        ):
            button = getattr(app, name, None)
            if button is not None:
                try:
                    button.configure(state="disabled" if active else "normal")
                except Exception:
                    LOGGER.debug("Import control was destroyed during state reset", exc_info=True)

    def rollback(error):
        LOGGER.error(
            "CSV import could not be applied",
            exc_info=(type(error), error, error.__traceback__),
        )
        app.tags = previous_tags
        if brand_changed:
            app.brand_menu.set(previous_brand)
            try:
                # The guard prevents update_brand from starting its own rebuild.
                app.update_brand(previous_brand)
            except Exception:
                LOGGER.exception("CSV import brand rollback failed")
        if runtime_snapshot is not None and hasattr(runtime_cache, "restore"):
            try:
                runtime_cache.restore(runtime_snapshot, previous_tags)
            except Exception:
                LOGGER.exception("CSV import runtime rollback failed")
        def recovery_complete():
            set_import_state(False)

        def recovery_failed(_error):
            LOGGER.exception("CSV import UI rollback refresh failed")
            set_import_state(False)

        try:
            if hasattr(app, "refresh_after_import"):
                app.refresh_after_import(recovery_complete, recovery_failed)
            else:
                refresh_tag_table(app)
                recovery_complete()
        except Exception:
            LOGGER.exception("CSV import UI rollback refresh failed")
            set_import_state(False)
        messagebox.showerror(
            error_title,
            "Import could not be completed. Your previous tags were restored.",
        )

    def complete():
        set_import_state(False)
        app.status_label.configure(
            text=f"● {len(imported_tags)} tags imported successfully",
            text_color="lime",
        )
        LOGGER.info("CSV import stage: import completed tags=%d", len(imported_tags))

    set_import_state(True)
    if hasattr(app, "status_label"):
        app.status_label.configure(text="● IMPORTING TAGS…", text_color="orange")

    try:
        app.tags = imported_tags
        mark_project_modified(app)
        LOGGER.info("CSV import stage: tags applied count=%d", len(imported_tags))
        if brand_changed:
            app.brand_menu.set(target_brand)
            app.update_brand(target_brand)
        if hasattr(app, "refresh_after_import"):
            app.refresh_after_import(complete, rollback)
            return True
        else:
            refresh_tag_table(app)
    except Exception as error:
        rollback(error)
        return False
    complete()
    return True


def export_tags_csv(app):
    file_path = filedialog.asksaveasfilename(
        initialdir="configs",
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")],
        initialfile="tags.csv",
    )
    if not file_path:
        return

    try:
        write_tags_csv(file_path, app.tags)
    except OSError as error:
        LOGGER.exception("Universal CSV export failed: %s", file_path)
        messagebox.showerror("Erro Export CSV", CSV_EXPORT_ERROR)
        return

    app.status_label.configure(
        text=f"● {len(app.tags)} TAGS EXPORTADAS",
        text_color="lime",
    )
    LOGGER.info("Universal CSV exported: %s", file_path)


def get_csv_template_path(brand):
    """Return the bundled CSV template for a PLC brand."""
    filename = TEMPLATE_FILENAMES.get(
        str(brand).strip(),
        "universal_tags_template.csv",
    )
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
    return bundle_root / "templates" / filename


def export_csv_template(app):
    template_path = get_csv_template_path(connection_brand(app))
    destination = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")],
        initialfile=template_path.name,
        confirmoverwrite=False,
    )
    if not destination:
        return

    destination_path = Path(destination)
    if destination_path.exists() and not messagebox.askyesno(
        "Substituir Template CSV",
        f"O ficheiro '{destination_path.name}' já existe. Substituir?",
    ):
        return

    try:
        shutil.copyfile(template_path, destination_path)
    except OSError as error:
        LOGGER.exception("CSV template export failed: %s", destination_path)
        messagebox.showerror("Erro Exportar Template CSV", CSV_EXPORT_ERROR)
        return

    app.status_label.configure(
        text=f"● TEMPLATE CSV EXPORTADO: {destination_path.name}",
        text_color="lime",
    )
    LOGGER.info("CSV template exported: %s", destination_path)


def refresh_tag_table(app, view_only=False):
    selected = app.tag_table.selection()
    selected_iid = selected[0] if selected else None
    query = (
        app.tag_search_entry.get().strip()
        if hasattr(app, "tag_search_entry") else ""
    )
    if query and selected_iid:
        app._tag_search_restore_iid = selected_iid
    children = app.tag_table.get_children()
    if children:
        app.tag_table.delete(*children)

    app.tag_table.tag_configure("even", background="#242424")
    app.tag_table.tag_configure("odd", background="#2b2b2b")

    filtered = filter_tag_collection(app.tags, query)
    indices = {id(tag): index for index, tag in enumerate(app.tags)}
    for visible_index, tag in enumerate(filtered):
        index = indices[id(tag)]
        create_tag_row(app, tag, index)

    visible_iids = set(app.tag_table.get_children())
    candidate = selected_iid if selected_iid in visible_iids else None
    if not query:
        restore = getattr(app, "_tag_search_restore_iid", None)
        if restore in visible_iids:
            candidate = restore
            app._tag_search_restore_iid = None
    if candidate is None and visible_iids:
        candidate = app.tag_table.get_children()[0]
    if candidate is not None:
        app.tag_table.selection_set(candidate)
        app.tag_table.focus(candidate)
        app.tag_table.see(candidate)

    if hasattr(app, "tag_search_count_label"):
        text = (
            f"Showing {len(filtered)} of {len(app.tags)} tags"
            if query else f"{len(app.tags)} tags"
        )
        app.tag_search_count_label.configure(text=text)

    if not view_only:
        update_master_tag_option_states(app)
        update_tag_database_validation(app)


def create_tag_row(app, tag, index=None):
    """Insert a lightweight native table row without per-cell widgets."""
    address_valid, _ = validate_tag_address(
        connection_brand(app),
        tag.data_type,
        tag.address,
    )
    marker = lambda value: "✓" if value else "—"
    iid = str(index if index is not None else len(app.tag_table.get_children()))
    app.tag_table.insert("", "end", iid=iid, values=(
        tag.name, tag.data_type, tag.direction,
        tag.address if address_valid else f"⚠ {tag.address}",
        marker(tag.enabled_sim), marker(tag.enabled_trend),
        marker(tag.enabled_alarm), marker(tag.enabled_dashboard), "Eliminar",
    ), tags=("even" if int(iid) % 2 == 0 else "odd",))


def on_tag_table_click(app, event):
    """Handle flag and delete cells without creating interactive row widgets."""
    table = app.tag_table
    item = table.identify_row(event.y)
    column = table.identify_column(event.x)
    if not item or not column:
        return
    try:
        tag = app.tags[int(item)]
    except (ValueError, IndexError):
        return

    column_number = int(column[1:])
    flag_fields = {
        5: "enabled_sim", 6: "enabled_trend",
        7: "enabled_alarm", 8: "enabled_dashboard",
    }
    if column_number in flag_fields:
        field = flag_fields[column_number]
        value = not getattr(tag, field)
        set_tag_flag(app, tag, field, value)
        table.set(item, field, "✓" if value else "—")
    elif column_number == 9:
        delete_tag(app, tag)


def update_master_tag_option_states(app, option_name=None):
    """Synchronize master checkboxes with current tag values."""
    checkboxes = getattr(app, "tag_master_checkboxes", {})
    options = (option_name,) if option_name else tuple(checkboxes)
    tags = app.tags
    for option in options:
        checkbox = checkboxes.get(option)
        if checkbox is None:
            continue
        enabled_count = sum(bool(getattr(tag, option)) for tag in tags)
        checkbox.state(["!selected", "!alternate"])
        if tags and enabled_count == len(tags):
            checkbox.state(["selected"])
        elif enabled_count:
            checkbox.state(["alternate"])


def on_master_tag_option_clicked(app, option_name):
    """Apply the clicked master state to all tags exactly once."""
    checkbox = app.tag_master_checkboxes[option_name]
    enabled = checkbox.instate(["selected"])
    set_all_tag_option(app, option_name, enabled)


def set_all_tag_option(app, option_name, enabled):
    """Set one option for every tag with one lightweight table refresh."""
    valid_options = {
        "enabled_sim", "enabled_trend", "enabled_alarm", "enabled_dashboard",
    }
    if option_name not in valid_options:
        raise ValueError(f"Unsupported tag option: {option_name}")

    changed = False
    for tag in app.tags:
        if getattr(tag, option_name) != enabled:
            setattr(tag, option_name, enabled)
            changed = True

    profile_changed = False
    if option_name == "enabled_sim":
        if enabled:
            profile_changed = _set_manual_analog_profiles_to_ramp(app)
        else:
            from ui.analog_profiles import canonical_analog_profile
            for tag in app.tags:
                if tag.direction == "Input" and tag.data_type in ("INT", "REAL"):
                    canonical_analog_profile(app, tag)
            manager = getattr(app, "analog_simulation_manager", None)
            if manager is not None:
                manager.stop_all()

    refresh_tag_table(app)
    if getattr(app, "_analog_structure_initialized", False):
        from ui.analog_tab import refresh_analog_tab
        refresh_analog_tab(app)
    if changed or profile_changed:
        mark_project_modified(app)
    if option_name == "enabled_sim" and enabled and hasattr(app, "status_label"):
        app.status_label.configure(
            text="All analog simulations enabled; Manual tags set to Ramp",
            text_color="lime",
        )


def _set_manual_analog_profiles_to_ramp(app):
    """Convert only Manual analog-input profiles for the bulk enable action."""
    from ui.analog_profiles import ensure_dynamic_analog_profiles
    analog_tags = [
        tag for tag in app.tags
        if tag.direction == "Input" and tag.data_type in ("INT", "REAL")
    ]
    if getattr(app, "_analog_structure_initialized", False):
        from ui.analog_tab import (
            commit_analog_editor_configuration,
            sync_selected_editor_from_canonical,
        )
        commit_analog_editor_configuration(app, mark_dirty=False)
    changed_names = ensure_dynamic_analog_profiles(app, analog_tags)
    if changed_names and getattr(app, "_analog_structure_initialized", False):
        sync_selected_editor_from_canonical(app)
    return bool(changed_names)


def mark_project_modified(app):
    """Notify applications with explicit dirty tracking once per user action."""
    callback = getattr(app, "mark_project_modified", None)
    if callable(callback):
        callback()


def set_tag_flag(app, tag, field, value):
    changed = getattr(tag, field) != value
    setattr(tag, field, value)
    if (
        field == "enabled_sim"
        and tag.direction == "Input"
        and tag.data_type in ("INT", "REAL")
    ):
        from ui.analog_profiles import canonical_analog_profile
        canonical_analog_profile(app, tag)
        if not value:
            manager = getattr(app, "analog_simulation_manager", None)
            if manager is not None:
                manager.stop(tag.name)
        if getattr(app, "_analog_structure_initialized", False):
            from ui.analog_tab import refresh_analog_tree_row
            refresh_analog_tree_row(app, tag.name)
    update_master_tag_option_states(app, field)
    if changed:
        mark_project_modified(app)


def delete_tag(app, tag):
    if tag in app.tags:
        app.tags.remove(tag)
        mark_project_modified(app)

    refresh_tag_table(app)
    app.generate_signals()


def is_tag_compatible(app, tag):
    valid, _ = validate_tag_address(
        connection_brand(app),
        tag.data_type,
        tag.address,
    )
    return valid


def get_invalid_tags_for_brand(app):
    return [
        tag for tag in getattr(app, "tags", [])
        if not is_tag_compatible(app, tag)
    ]


def update_tag_database_validation(app):
    if not hasattr(app, "tag_database_validation_label"):
        return

    invalid_tags = get_invalid_tags_for_brand(app)
    if invalid_tags:
        names = ", ".join(tag.name or "<sem nome>" for tag in invalid_tags)
        app.tag_database_validation_label.configure(
            text=(
                f"⚠ {len(invalid_tags)} tag(s) incompatível(is) com "
                f"{connection_brand(app)}: {names}. Ignoradas pelos separadores runtime."
            ),
            text_color="red",
        )
    else:
        app.tag_database_validation_label.configure(
            text="Todas as tags são compatíveis com a marca selecionada",
            text_color="lime",
        )


def get_input_bool_tags(app):
    return [
        tag for tag in app.tags
        if tag.direction == "Input"
        and tag.data_type == "BOOL"
        and tag.enabled_sim
        and is_tag_compatible(app, tag)
    ]


def get_input_analog_tags(app):
    """Return analog inputs for both interactive and PLC read-only rows."""
    return [
        tag for tag in app.tags
        if tag.direction == "Input"
        and tag.data_type in ["INT", "REAL"]
        and is_tag_compatible(app, tag)
    ]


def get_trend_tags(app):
    return [
        tag for tag in app.tags
        if tag.enabled_trend
        and is_tag_compatible(app, tag)
    ]


def get_alarm_tags(app):
    return [
        tag for tag in app.tags
        if tag.enabled_alarm
        and is_tag_compatible(app, tag)
    ]


def get_dashboard_tags(app):
    return [
        tag for tag in getattr(app, "tags", [])
        if tag.enabled_dashboard
        and is_tag_compatible(app, tag)
    ]


def get_numeric_tags(app):
    return [
        tag for tag in getattr(app, "tags", [])
        if tag.data_type in ["INT", "REAL"]
        and is_tag_compatible(app, tag)
    ]


def get_pid_output_tags(app):
    return [
        tag for tag in get_numeric_tags(app)
        if tag.direction in ["Input", "Internal", "Output"]
    ]


def get_tag_by_name(app, name):
    return next(
        (tag for tag in getattr(app, "tags", []) if tag.name == name),
        None,
    )


def get_feedback_tags(app):
    return [
        tag for tag in app.tags
        if tag.direction == "Feedback"
        and is_tag_compatible(app, tag)
    ]
