from pathlib import Path

from services import storage_paths
from ui import project_config, tag_manager, trend_tab


def test_storage_directories_are_created(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    storage_paths.ensure_storage_directories()
    assert (tmp_path / "configs").is_dir()
    assert (tmp_path / "configs" / "projects").is_dir()
    assert (tmp_path / "configs" / "csv").is_dir()


def test_legacy_project_is_redirected_only_when_saved(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    legacy = tmp_path / "configs" / "Legacy.simproject"
    legacy.parent.mkdir()
    legacy.write_text("{}", encoding="utf-8")
    redirected = storage_paths.future_project_path(str(legacy))
    assert Path(redirected) == Path("configs/projects/Legacy.simproject")
    assert legacy.exists()


def test_project_dialogs_start_in_projects_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(project_config.filedialog, "askopenfilename", lambda **kwargs: calls.append(kwargs) or "")
    assert project_config.open_project(object()) is False
    assert calls[0]["initialdir"] == "configs/projects"


def test_save_as_starts_in_projects_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(project_config.filedialog, "asksaveasfilename", lambda **kwargs: calls.append(kwargs) or "")
    assert project_config.save_project_as(object()) is False
    assert calls[0]["initialdir"] == "configs/projects"


def test_saving_open_legacy_project_uses_projects_directory(tmp_path, project_app, monkeypatch):
    monkeypatch.chdir(tmp_path)
    legacy = tmp_path / "configs" / "Legacy.simproject"
    legacy.parent.mkdir()
    legacy.write_text("old content", encoding="utf-8")
    project_app.project_path = str(legacy)
    assert project_config.save_project(project_app)
    assert Path(project_app.project_path) == Path("configs/projects/Legacy.simproject")
    assert legacy.read_text(encoding="utf-8") == "old content"
    assert (tmp_path / project_app.project_path).is_file()


def test_csv_dialogs_start_in_csv_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(tag_manager.filedialog, "askopenfilename", lambda **kwargs: calls.append(kwargs) or "")
    tag_manager.import_tags_csv(object())
    monkeypatch.setattr(trend_tab.filedialog, "asksaveasfilename", lambda **kwargs: calls.append(kwargs) or "")
    trend_tab.export_csv(object())
    assert [call["initialdir"] for call in calls] == ["configs/csv", "configs/csv"]
