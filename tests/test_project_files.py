import json

from ui import project_config


def test_save_and_load_project_headlessly(tmp_path, project_app):
    path = tmp_path / "roundtrip.simproject"

    assert project_config._write_project(project_app, path)
    with path.open(encoding="utf-8") as project_file:
        loaded = json.load(project_file)
    staged = project_config._stage_project_data(loaded)

    assert staged["format"] == project_config.PROJECT_FORMAT
    assert staged["plc"]["brand"] == "Siemens"
    assert [tag["name"] for tag in staged["tags"]] == ["Run", "Speed"]
    assert staged["tags"][1]["data_type"] == "REAL"


def test_corrupted_project_is_rejected(tmp_path, monkeypatch):
    path = tmp_path / "corrupt.simproject"
    path.write_text('{"format": broken json', encoding="utf-8")
    errors = []
    monkeypatch.setattr(
        project_config.filedialog,
        "askopenfilename",
        lambda **_kwargs: str(path),
    )
    monkeypatch.setattr(
        project_config.messagebox,
        "showerror",
        lambda title, message: errors.append((title, message)),
    )

    assert project_config.open_project(object()) is False
    assert errors
    assert "abrir projeto" in errors[0][0]
