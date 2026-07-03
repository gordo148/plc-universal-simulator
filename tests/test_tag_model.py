import pytest

from core.tag_model import TagDefinition
from ui.tag_manager import normalize_and_validate_tag_names


@pytest.mark.parametrize(
    ("data_type", "address"),
    [("BOOL", "DBX0.0"), ("INT", "DBW10"), ("REAL", "DBD20")],
)
def test_create_supported_tag_types(data_type, address):
    tag = TagDefinition("Tag1", data_type, "Input", address)

    assert tag.name == "Tag1"
    assert tag.data_type == data_type
    assert tag.address == address


def test_reject_empty_tag_name():
    valid, message = normalize_and_validate_tag_names([
        TagDefinition("   ", "BOOL", "Input", "DBX0.0")
    ])

    assert not valid
    assert "vazio" in message


def test_reject_duplicate_tag_names_case_insensitively():
    valid, message = normalize_and_validate_tag_names([
        TagDefinition("Motor", "BOOL", "Input", "DBX0.0"),
        TagDefinition(" motor ", "INT", "Input", "DBW10"),
    ])

    assert not valid
    assert "duplicado" in message
