"""Tests for version generation without requiring a Git repository."""

from pathlib import Path

import pytest

from scripts import generate_version
from scripts.generate_version import (
    GitUnavailableError,
    determine_version,
    parse_semver_tag,
)


@pytest.mark.parametrize(
    ("tag_name", "version", "release"),
    [
        ("v2.2.1", "2.2.1", "Stable"),
        ("v2.2.2", "2.2.2", "Stable"),
        ("v2.3.0-alpha1", "2.3.0-alpha1", "Alpha"),
        ("v2.3.0-beta2", "2.3.0-beta2", "Beta"),
        ("v2.3.0-rc1", "2.3.0-rc1", "Release Candidate"),
    ],
)
def test_exact_semver_tags(tag_name, version, release):
    result = determine_version([tag_name], [tag_name], {tag_name: 0}, "abc1234", False)

    assert result.version == version
    assert result.release == release
    assert result.selected_tag == tag_name


@pytest.mark.parametrize(
    ("dirty", "expected"),
    [
        (False, "2.2.2+3.gabc1234"),
        (True, "2.2.2+3.gabc1234.dirty"),
    ],
)
def test_commit_after_nearest_tag(dirty, expected):
    result = determine_version(
        ["v2.2.2"],
        [],
        {"v2.2.2": 3},
        "abc1234",
        dirty,
    )

    assert result.version == expected
    assert result.release == "Development"


def test_dirty_exact_tag_is_a_development_build():
    result = determine_version(
        ["v2.2.2"],
        ["v2.2.2"],
        {"v2.2.2": 0},
        "abc1234",
        True,
    )

    assert result.version == "2.2.2+0.gabc1234.dirty"
    assert result.release == "Development"


def test_plain_commit_hash_without_valid_tag():
    result = determine_version([], [], {}, "abc1234", False)

    assert result.version == "0.0.0+gabc1234"
    assert result.release == "Development"
    assert result.selected_tag is None


@pytest.mark.parametrize(
    "tag_name",
    [
        "2.2.2",
        "v2.2",
        "v2.2.2.1",
        "v02.2.2",
        "v2.2.2-preview1",
        "v2.2.2-stable",
        "release-v2.2.2",
    ],
)
def test_malformed_and_prefixless_tags_are_rejected(tag_name):
    assert parse_semver_tag(tag_name) is None


def test_malformed_tags_do_not_override_nearest_valid_tag():
    result = determine_version(
        ["v9.9-latest", "v2.2.2"],
        [],
        {"v2.2.2": 2},
        "abc1234",
        False,
    )

    assert result.version == "2.2.2+2.gabc1234"
    assert result.selected_tag == "v2.2.2"


def test_nearest_history_tag_wins_over_higher_unrelated_version():
    result = determine_version(
        ["v2.2.2", "v3.0.0"],
        [],
        {"v2.2.2": 2, "v3.0.0": 8},
        "abc1234",
        False,
    )

    assert result.selected_tag == "v2.2.2"
    assert result.warnings == ("Multiple reachable major release lines detected: v2.x, v3.x",)


def test_exact_tag_wins_and_multiple_major_lines_generate_warning():
    result = determine_version(
        ["v1.1.1", "v2.2.1"],
        ["v1.1.1"],
        {"v1.1.1": 0, "v2.2.1": 1},
        "abc1234",
        False,
    )

    assert result.version == "1.1.1"
    assert result.selected_tag == "v1.1.1"
    assert result.warnings == ("Multiple reachable major release lines detected: v1.x, v2.x",)


def test_git_unavailable_uses_committed_values(monkeypatch, tmp_path, capsys):
    version_module = Path(tmp_path, "version.py")
    version_module.write_text(
        'APP_VERSION = "2.2.2"\nAPP_RELEASE = "Stable"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(generate_version, "VERSION_MODULE", version_module)
    monkeypatch.setattr(
        generate_version,
        "inspect_repository",
        lambda: (_ for _ in ()).throw(GitUnavailableError("Git unavailable")),
    )

    assert generate_version.main() == 0
    output = capsys.readouterr()
    assert "using committed fallback 2.2.2" in output.err
    assert "Detected application version: 2.2.2" in output.out
    generated = version_module.read_text(encoding="utf-8")
    assert "APP_VERSION = '2.2.2'" in generated
    assert "APP_GIT_COMMIT = 'Unknown'" in generated
    assert "APP_GIT_BRANCH = 'Unknown'" in generated
    assert "APP_BUILD_DATE = '" in generated


def test_rendered_module_contains_all_build_metadata():
    rendered = generate_version.render_version_module(
        "2.2.2", "Stable", "3bc826a", "main", "2026-07-10 18:45 UTC"
    )

    assert "APP_NAME = 'PLC Universal Simulator'" in rendered
    assert "APP_VERSION = '2.2.2'" in rendered
    assert "APP_RELEASE = 'Stable'" in rendered
    assert "APP_GIT_COMMIT = '3bc826a'" in rendered
    assert "APP_GIT_BRANCH = 'main'" in rendered
    assert "APP_BUILD_DATE = '2026-07-10 18:45 UTC'" in rendered
