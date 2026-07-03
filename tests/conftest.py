from types import SimpleNamespace

import pytest

from core.tag_model import TagDefinition


class Value:
    """Small headless replacement for Tk variables and entry widgets."""

    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class Recorder:
    def __init__(self):
        self.calls = []

    def configure(self, **kwargs):
        self.calls.append(kwargs)


@pytest.fixture
def project_app():
    app = SimpleNamespace(
        brand_menu=Value("Siemens"),
        ip_entry=Value("192.168.1.10"),
        rack_entry=Value("0"),
        slot_entry=Value("1"),
        db_entry=Value("100"),
        tags=[
            TagDefinition("Run", "BOOL", "Input", "DBX0.0", True),
            TagDefinition("Speed", "REAL", "Output", "DBD20"),
        ],
        digital_widgets=[],
        analog_widgets=[],
        alarms=[],
        trend_tag_vars={},
        trend_auto_scale=Value(True),
        pid_sp_entry=Value("10"),
        pid_sp_source_menu=Value("MANUAL"),
        pid_pv_menu=Value("Speed"),
        pid_out_menu=Value("Speed"),
        pid_kp_entry=Value("1"),
        pid_ki_entry=Value("0"),
        pid_kd_entry=Value("0"),
        pid_out_min_entry=Value("0"),
        pid_out_max_entry=Value("100"),
        pid_interval_entry=Value("500"),
        status_label=Recorder(),
        app=SimpleNamespace(title=lambda _title: None),
        project_path=None,
    )
    return app
