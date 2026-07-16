from ui.project_config import migrate_project_data


def _project(tags):
    return {
        "format": "plc-universal-simulator-project", "version": 1,
        "plc": {"brand": "Siemens", "ip": "", "settings": {"rack": "0", "slot": "1", "db_number": "2000"}},
        "tags": tags,
    }


def test_migrates_all_legacy_widths_and_removes_global_db():
    types = ["BOOL", "BYTE", "WORD", "INT", "DWORD", "DINT", "REAL"]
    tags = [{"name": kind, "data_type": kind, "direction": "Input", "offset": 4, "bit": 3} for kind in types]
    migrated = migrate_project_data(_project(tags))
    assert migrated["schema_version"] == 2
    assert "db_number" not in migrated["plc"]["settings"]
    assert [tag["address"] for tag in migrated["tags"]] == [
        "%DB2000.DBX4.3", "%DB2000.DBB4", "%DB2000.DBW4", "%DB2000.DBW4",
        "%DB2000.DBD4", "%DB2000.DBD4", "%DB2000.DBD4",
    ]


def test_migrates_legacy_address_and_skips_only_invalid_tag():
    source = _project([
        {"name": "Good", "data_type": "BOOL", "direction": "Feedback", "address": "DBX4.0"},
        {"name": "Bad", "data_type": "REAL", "direction": "Feedback", "address": "broken"},
    ])
    migrated = migrate_project_data(source)
    assert source["tags"][0]["address"] == "DBX4.0"
    assert [tag["name"] for tag in migrated["tags"]] == ["Good"]
    assert "Bad" in migrated["_migration_warnings"][0]
