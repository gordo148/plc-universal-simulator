from pathlib import Path
import subprocess
import sys

import pytest

from services import plc_service
from services.plc_service import PLCService


def test_application_ui_import_does_not_load_plc_drivers():
    project_root = Path(__file__).resolve().parent.parent
    script = """
import sys

class BlockPLCImports:
    blocked = {"snap7", "pymodbus", "pycomm3", "fins"}

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in self.blocked:
            raise ModuleNotFoundError(fullname)
        return None

sys.meta_path.insert(0, BlockPLCImports())
import main
from services.plc_service import PLCService

service = PLCService()
assert service.connect("Simulator", "")
assert service.is_connected()
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr


def test_missing_physical_driver_does_not_block_internal_simulator(
    monkeypatch,
):
    original_import = plc_service._DRIVER_IMPORTS["SiemensS7Driver"]
    monkeypatch.setitem(
        plc_service._DRIVER_IMPORTS,
        "SiemensS7Driver",
        "missing_plc_library.siemens",
    )
    monkeypatch.setattr(plc_service, "SiemensS7Driver", None)

    service = PLCService()
    with pytest.raises(ModuleNotFoundError):
        service.connect("Siemens", "192.0.2.1")

    monkeypatch.setitem(
        plc_service._DRIVER_IMPORTS,
        "SiemensS7Driver",
        original_import,
    )
    assert service.connect("Simulator", "") is True
    assert service.is_connected() is True
