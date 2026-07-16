"""Canonical user-file locations used by dialogs and new saves."""

from pathlib import Path


CONFIG_DIRECTORY = Path("configs")
PROJECT_DIRECTORY = CONFIG_DIRECTORY / "projects"
CSV_DIRECTORY = CONFIG_DIRECTORY / "csv"


def ensure_storage_directories():
    """Create the user-file layout and return its three directories."""
    for directory in (CONFIG_DIRECTORY, PROJECT_DIRECTORY, CSV_DIRECTORY):
        directory.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIRECTORY, PROJECT_DIRECTORY, CSV_DIRECTORY


def project_directory():
    ensure_storage_directories()
    return str(PROJECT_DIRECTORY)


def csv_directory():
    ensure_storage_directories()
    return str(CSV_DIRECTORY)


def future_project_path(file_path):
    """Redirect only legacy projects directly under configs on their next save."""
    path = Path(file_path)
    try:
        is_legacy = path.resolve().parent == CONFIG_DIRECTORY.resolve()
    except OSError:
        is_legacy = False
    if is_legacy:
        ensure_storage_directories()
        return str(PROJECT_DIRECTORY / path.name)
    return file_path
