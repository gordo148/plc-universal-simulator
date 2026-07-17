import subprocess
import sys

from ui import project_config


def test_main_import_does_not_load_heavy_optional_modules():
    code = """
import sys
import main
heavy = {'matplotlib', 'snap7', 'pymodbus', 'pycomm3', 'fins'}
loaded = sorted(heavy.intersection(sys.modules))
raise SystemExit(f'loaded unexpectedly: {loaded}' if loaded else 0)
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_project_build_before_opening_trends_uses_safe_defaults(project_app):
    del project_app.trend_auto_scale
    project_app.trend_tag_vars = {}

    project = project_config.build_project_data(project_app)

    assert project["trends"]["auto_scale"] is True
    assert project["trends"]["selected_curve_ids"] == []


def test_unopened_trend_settings_are_deferred_and_preserved(project_app):
    del project_app.trend_auto_scale
    del project_app.trend_tag_vars
    project_app.ensure_trend_tab = lambda: None
    project_app._trend_initialized = False
    settings = {
        "selected_curves": ["Speed"],
        "auto_scale": False,
    }

    project_config._restore_trends(project_app, settings)
    project = project_config.build_project_data(project_app)

    assert project_app._pending_trend_settings == settings
    speed = next(tag for tag in project_app.tags if tag.name == "Speed")
    assert project["trends"]["selected_curve_ids"] == [speed.tag_id]
    assert project["trends"]["auto_scale"] is False
