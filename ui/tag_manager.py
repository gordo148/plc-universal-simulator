import csv
import customtkinter as ctk
import re
from tkinter import filedialog, messagebox

from core.tag_model import Tag


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

TRUE_CSV_VALUES = {"1", "true", "yes"}
FALSE_CSV_VALUES = {"0", "false", "no"}


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

    ctk.CTkButton(
        controls,
        text="Suggest Address",
        command=lambda: suggest_tag_address(app),
        width=125,
    ).pack(side="left", padx=5)

    ctk.CTkButton(
        controls,
        text="Adicionar Tag",
        command=lambda: add_tag(app),
        width=130
    ).pack(side="left", padx=10)

    ctk.CTkButton(
        controls,
        text="Atualizar Sinais",
        command=lambda: app.generate_signals(),
        width=130
    ).pack(side="left", padx=5)

    ctk.CTkButton(
        controls,
        text="Import CSV",
        command=lambda: import_tags_csv(app),
        width=110,
    ).pack(side="left", padx=5)

    ctk.CTkButton(
        controls,
        text="Import TIA CSV",
        command=lambda: import_tia_csv(app),
        width=120,
    ).pack(side="left", padx=5)

    ctk.CTkButton(
        controls,
        text="Import Schneider CSV",
        command=lambda: import_schneider_csv(app),
        width=155,
    ).pack(side="left", padx=5)

    ctk.CTkButton(
        controls,
        text="Export CSV",
        command=lambda: export_tags_csv(app),
        width=110,
    ).pack(side="left", padx=5)

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

    header = ctk.CTkFrame(frame)
    header.pack(fill="x", padx=10, pady=(10, 0))

    create_header_cell(header, "Nome", 0, COL_WIDTHS["name"])
    create_header_cell(header, "Tipo", 1, COL_WIDTHS["type"])
    create_header_cell(header, "Direção", 2, COL_WIDTHS["direction"])
    create_header_cell(header, "Endereço", 3, COL_WIDTHS["address"])
    create_header_cell(header, "Sim", 4, COL_WIDTHS["sim"])
    create_header_cell(header, "Trend", 5, COL_WIDTHS["trend"])
    create_header_cell(header, "Alarme", 6, COL_WIDTHS["alarm"])
    create_header_cell(header, "Dash", 7, COL_WIDTHS["dash"])
    create_header_cell(header, "Ação", 8, COL_WIDTHS["delete"])

    app.tag_table = ctk.CTkScrollableFrame(frame)
    app.tag_table.pack(fill="both", expand=True, padx=10, pady=10)

    refresh_tag_table(app)
    update_tag_address_context(app)


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
    address = app.tag_address_entry.get().strip().upper()
    valid, validation_message = validate_tag_address(
        app.brand_menu.get(),
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
    else:
        return False, f"Marca PLC não suportada: {brand}"

    rule = patterns.get(data_type)
    if rule is None:
        return False, f"Tipo de dados não suportado: {data_type}"

    pattern, error_message = rule
    if re.fullmatch(pattern, address) is None:
        return False, error_message

    if brand == "Schneider" and data_type == "REAL":
        return True, "Endereço válido; REAL ocupa 2 registos %MW"
    return True, "Endereço válido"


def suggest_tag_address(app):
    address = suggest_address(
        app.brand_menu.get(),
        app.tag_type_menu.get(),
        app.tags,
    )
    app.tag_address_entry.delete(0, "end")
    app.tag_address_entry.insert(0, address)
    app.tag_address_manual_edit = False
    app.tag_last_suggested_address = address

    _, message = validate_tag_address(
        app.brand_menu.get(),
        app.tag_type_menu.get(),
        address,
    )
    app.tag_validation_label.configure(
        text=f"Sugestão: {address} — {message}",
        text_color="cyan",
    )


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
        app.brand_menu.get(),
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

    address = app.tag_address_entry.get().strip()
    if not address or not getattr(app, "tag_address_manual_edit", False):
        suggest_tag_address(app)
    else:
        validate_current_tag_address(app)


def suggest_address(brand, data_type, tags):
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

    if brand == "Schneider":
        occupied_coils, occupied_registers = _schneider_occupancy(tags)

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
    occupied_coils = set()
    occupied_registers = set()

    for tag in tags:
        valid, _ = validate_tag_address("Schneider", tag.data_type, tag.address)
        if not valid:
            continue

        address = tag.address.strip().upper()
        if tag.data_type == "BOOL":
            occupied_coils.add(int(address.removeprefix("%M")))
        else:
            register = int(address.removeprefix("%MW"))
            count = 2 if tag.data_type == "REAL" else 1
            occupied_registers.update(range(register, register + count))

    return occupied_coils, occupied_registers


def parse_csv_bool(value):
    normalized = str(value).strip().lower()
    if normalized in TRUE_CSV_VALUES:
        return True
    if normalized in FALSE_CSV_VALUES:
        return False
    raise ValueError(f"valor booleano inválido: {value}")


def read_tags_csv(file_path, brand=None):
    tags = []

    with open(file_path, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError("CSV sem cabeçalho")

        header_map = {
            str(header).strip().lower(): header
            for header in reader.fieldnames
        }
        missing_fields = [
            field for field in TAG_CSV_FIELDS
            if field not in header_map
        ]
        if missing_fields:
            raise ValueError(
                "colunas em falta: " + ", ".join(missing_fields)
            )

        direction_names = {
            "input": "Input",
            "feedback": "Feedback",
            "output": "Output",
            "internal": "Internal",
        }

        for line_number, row in enumerate(reader, start=2):
            if not any(str(value or "").strip() for value in row.values()):
                continue

            try:
                values = {
                    field: str(row.get(header_map[field], "") or "").strip()
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

                address = values["address"].upper()
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

    with open(file_path, "r", newline="", encoding="utf-8-sig") as file:
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

    with open(file_path, "r", newline="", encoding="utf-8-sig") as file:
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
        imported_tags = read_tags_csv(file_path, app.brand_menu.get())
    except (OSError, ValueError) as error:
        messagebox.showerror("Erro Import CSV", str(error))
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
        messagebox.showerror("Erro Import TIA CSV", str(error))
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
        messagebox.showerror("Erro Import Schneider CSV", str(error))
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
    names_valid, names_message = normalize_and_validate_tag_names(
        imported_tags
    )
    if not names_valid:
        messagebox.showerror(error_title, names_message)
        return False

    previous_tags = app.tags
    previous_brand = None
    brand_changed = False
    if (
        target_brand is not None
        and hasattr(app, "brand_menu")
        and hasattr(app, "update_brand")
    ):
        previous_brand = app.brand_menu.get()
        brand_changed = previous_brand != target_brand

    try:
        app.tags = imported_tags
        refresh_tag_table(app)
        if brand_changed:
            app.brand_menu.set(target_brand)
            app.update_brand(target_brand)
        else:
            app.generate_signals()
    except Exception as error:
        app.tags = previous_tags
        refresh_tag_table(app)
        if brand_changed:
            app.brand_menu.set(previous_brand)
            app.update_brand(previous_brand)
        else:
            app.generate_signals()
        messagebox.showerror(error_title, str(error))
        return False

    app.status_label.configure(
        text=success_text,
        text_color="lime",
    )
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
        messagebox.showerror("Erro Export CSV", str(error))
        return

    app.status_label.configure(
        text=f"● {len(app.tags)} TAGS EXPORTADAS",
        text_color="lime",
    )


def refresh_tag_table(app):
    for widget in app.tag_table.winfo_children():
        widget.destroy()

    for tag in app.tags:
        create_tag_row(app, tag)

    update_tag_database_validation(app)


def create_tag_row(app, tag):
    row = ctk.CTkFrame(app.tag_table)
    row.pack(fill="x", padx=5, pady=4)

    ctk.CTkLabel(row, text=tag.name, width=COL_WIDTHS["name"], anchor="w").grid(row=0, column=0, padx=4, pady=5)
    ctk.CTkLabel(row, text=tag.data_type, width=COL_WIDTHS["type"], anchor="center").grid(row=0, column=1, padx=4)
    ctk.CTkLabel(row, text=tag.direction, width=COL_WIDTHS["direction"], anchor="center").grid(row=0, column=2, padx=4)
    address_valid, _ = validate_tag_address(
        app.brand_menu.get(),
        tag.data_type,
        tag.address,
    )
    ctk.CTkLabel(
        row,
        text=tag.address if address_valid else f"⚠ {tag.address}",
        text_color="white" if address_valid else "red",
        width=COL_WIDTHS["address"],
        anchor="center",
    ).grid(row=0, column=3, padx=4)

    sim_var = ctk.BooleanVar(value=tag.enabled_sim)
    trend_var = ctk.BooleanVar(value=tag.enabled_trend)
    alarm_var = ctk.BooleanVar(value=tag.enabled_alarm)
    dash_var = ctk.BooleanVar(value=tag.enabled_dashboard)

    ctk.CTkCheckBox(
        row,
        text="",
        variable=sim_var,
        command=lambda: set_tag_flag(app, tag, "enabled_sim", sim_var.get()),
        width=COL_WIDTHS["sim"]
    ).grid(row=0, column=4, padx=4)

    ctk.CTkCheckBox(
        row,
        text="",
        variable=trend_var,
        command=lambda: set_tag_flag(app, tag, "enabled_trend", trend_var.get()),
        width=COL_WIDTHS["trend"]
    ).grid(row=0, column=5, padx=4)

    ctk.CTkCheckBox(
        row,
        text="",
        variable=alarm_var,
        command=lambda: set_tag_flag(app, tag, "enabled_alarm", alarm_var.get()),
        width=COL_WIDTHS["alarm"]
    ).grid(row=0, column=6, padx=4)

    ctk.CTkCheckBox(
        row,
        text="",
        variable=dash_var,
        command=lambda: set_tag_flag(app, tag, "enabled_dashboard", dash_var.get()),
        width=COL_WIDTHS["dash"]
    ).grid(row=0, column=7, padx=4)

    ctk.CTkButton(
        row,
        text="Eliminar",
        width=COL_WIDTHS["delete"],
        fg_color="#8b1e1e",
        hover_color="#a83232",
        command=lambda: delete_tag(app, tag)
    ).grid(row=0, column=8, padx=4)


def set_tag_flag(app, tag, field, value):
    setattr(tag, field, value)

    if field == "enabled_sim":
        app.generate_signals()
    elif field == "enabled_trend" and hasattr(app, "trend_selector_frame"):
        from ui.trend_tab import refresh_trend_selectors

        refresh_trend_selectors(app)
    elif field == "enabled_alarm" and hasattr(app, "alarm_source_menu"):
        from ui.alarm_tab import update_alarm_sources

        update_alarm_sources(app)
    elif field == "enabled_dashboard" and hasattr(app, "dashboard_tags_frame"):
        from ui.dashboard_tab import update_dashboard

        update_dashboard(app, "Dashboard atualizado")

    if field != "enabled_sim" and hasattr(app, "update_pid_sources"):
        app.update_pid_sources()


def delete_tag(app, tag):
    if tag in app.tags:
        app.tags.remove(tag)

    refresh_tag_table(app)
    app.generate_signals()


def is_tag_compatible(app, tag):
    valid, _ = validate_tag_address(
        app.brand_menu.get(),
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
                f"{app.brand_menu.get()}: {names}. Ignoradas pelos separadores runtime."
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
    return [
        tag for tag in app.tags
        if tag.direction == "Input"
        and tag.data_type in ["INT", "REAL"]
        and tag.enabled_sim
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
