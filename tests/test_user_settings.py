import json
from pathlib import Path

from services.settings_service import ApplicationSettings, default_settings_path
from ui.main_window import PLCSimulator


def test_application_settings_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    settings = ApplicationSettings(
        plc_brand="Rockwell",
        ip_address="10.0.0.20",
        last_project_path="/projects/line.simproject",
        window_size="1280x800",
        recent_projects=["/projects/line.simproject"],
        last_project_folder="/projects",
        ui_preferences={"appearance_mode": "light"},
    )

    settings.save(path)
    loaded = ApplicationSettings.load(path)

    assert loaded == settings


def test_default_settings_path_uses_project_config_directory():
    assert Path(default_settings_path()).parts[-2:] == (
        "config",
        "settings.json",
    )


def test_corrupted_settings_use_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{bad json", encoding="utf-8")

    assert ApplicationSettings.load(path) == ApplicationSettings()


def test_recent_projects_are_unique_and_limited_to_five(tmp_path):
    settings = ApplicationSettings()
    paths = [tmp_path / f"project-{index}.simproject" for index in range(6)]
    for path in paths:
        settings.add_recent_project(str(path))
    settings.add_recent_project(str(paths[3]))

    assert len(settings.recent_projects) == 5
    assert settings.recent_projects[0] == str(paths[3])
    assert len(set(settings.recent_projects)) == 5
    assert settings.last_project_path == str(paths[3])
    assert settings.last_project_folder == str(tmp_path)


def test_invalid_saved_preferences_are_sanitized(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({
        "plc_brand": "Unknown",
        "ip_address": 123,
        "window_size": "huge",
        "recent_projects": "not-a-list",
    }), encoding="utf-8")

    assert ApplicationSettings.load(path) == ApplicationSettings()


def test_close_is_cancelled_when_unsaved_changes_are_not_discarded(monkeypatch):
    destroyed = []
    simulator = object.__new__(PLCSimulator)
    simulator.app = type("Window", (), {
        "destroy": lambda self: destroyed.append(True),
        "lift": lambda self: None,
        "focus_force": lambda self: None,
        "attributes": lambda self, *_args: None,
        "bell": lambda self: None,
    })()
    simulator.has_unsaved_changes = lambda: True
    simulator._save_settings = lambda: None
    monkeypatch.setattr("ui.main_window.messagebox.askyesno", lambda *_args, **_kwargs: False)

    simulator.on_close()

    assert destroyed == []


def test_project_snapshot_detects_persistent_changes(project_app):
    simulator = object.__new__(PLCSimulator)
    simulator.__dict__.update(project_app.__dict__)
    simulator._mark_project_saved()

    assert simulator.has_unsaved_changes() is False

    simulator.tags[0].address = "DBX1.0"

    assert simulator.has_unsaved_changes() is True
