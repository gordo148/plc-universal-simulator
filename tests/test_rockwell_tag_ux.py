from types import SimpleNamespace

from ui.tag_manager import resolve_tag_address, update_tag_address_context


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class Entry(Value):
    def __init__(self, value):
        super().__init__(value)
        self.manager = "pack"

    def delete(self, _start, _end):
        self.value = ""

    def insert(self, _index, value):
        self.value = value

    def winfo_manager(self):
        return self.manager

    def pack_forget(self):
        self.manager = ""

    def pack(self, **_kwargs):
        self.manager = "pack"


class Label:
    def configure(self, **_kwargs):
        pass


def test_rockwell_tag_name_resolves_to_symbolic_address():
    assert resolve_tag_address("Rockwell", "Motor_Run", "DBX0.0") == "Motor_Run"


def test_non_rockwell_address_resolution_is_unchanged():
    assert resolve_tag_address("Siemens", "Motor_Run", "dbx0.0") == "DBX0.0"
    assert resolve_tag_address("Schneider", "Motor_Run", "%m0") == "%M0"
    assert resolve_tag_address("Modbus TCP", "Motor_Run", "mw10") == "MW10"


def test_rockwell_context_hides_address_entry_and_keeps_internal_address():
    entry = Entry("DBX0.0")
    app = SimpleNamespace(
        brand_menu=Value("Rockwell"),
        tag_name_entry=Value("Motor_Run"),
        tag_type_menu=Value("BOOL"),
        tag_address_entry=entry,
        tag_validation_label=Label(),
    )

    update_tag_address_context(app)

    assert entry.winfo_manager() == ""
    assert entry.get() == "Motor_Run"
