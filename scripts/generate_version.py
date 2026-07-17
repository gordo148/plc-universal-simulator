#!/usr/bin/env python3
"""Generate the runtime version module from reachable semantic Git tags."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import ast
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

APP_NAME = "PLC Universal Simulator"
SOURCE_BUILD_TYPE = "Source development build"
FALLBACK_VERSION = "0.0.0-dev"
FALLBACK_RELEASE = "Development"
UNKNOWN = "Unknown"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_VERSION_MODULE = PROJECT_ROOT / "core" / "version.py"
BUILD_METADATA_MODULE = PROJECT_ROOT / "core" / "generated" / "build_metadata.py"

SEMVER_TAG_PATTERN = re.compile(
    r"^v(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<kind>alpha|beta|rc)(?P<number>0|[1-9]\d*))?$",
    re.IGNORECASE,
)
PRERELEASE_ORDER = {"alpha": 0, "beta": 1, "rc": 2}


class GitUnavailableError(RuntimeError):
    """Raised when Git or repository metadata cannot be used."""


@dataclass(frozen=True)
class SemanticTag:
    """A validated application release tag."""

    name: str
    version: str
    major: int
    minor: int
    patch: int
    prerelease: str | None
    prerelease_number: int | None

    @property
    def sort_key(self) -> tuple[int, int, int, int, int, int]:
        """Return a key implementing the supported SemVer precedence rules."""
        if self.prerelease is None:
            return self.major, self.minor, self.patch, 1, 0, 0
        return (
            self.major,
            self.minor,
            self.patch,
            0,
            PRERELEASE_ORDER[self.prerelease],
            self.prerelease_number or 0,
        )


@dataclass(frozen=True)
class VersionResult:
    """Version metadata selected for a build."""

    version: str
    release: str
    selected_tag: str | None
    warnings: tuple[str, ...] = ()
    git_commit: str = UNKNOWN
    git_branch: str = UNKNOWN
    commit_timestamp: int | None = None


def parse_semver_tag(tag_name: str) -> SemanticTag | None:
    """Parse a supported ``vMAJOR.MINOR.PATCH`` tag, or reject it."""
    match = SEMVER_TAG_PATTERN.fullmatch(tag_name.strip())
    if match is None:
        return None
    kind = match.group("kind")
    number = match.group("number")
    version = tag_name.strip()[1:]
    return SemanticTag(
        name=tag_name.strip(),
        version=version,
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        prerelease=kind.lower() if kind else None,
        prerelease_number=int(number) if number is not None else None,
    )


def release_type(tag: SemanticTag) -> str:
    """Return the release label for an exact, clean semantic tag."""
    if tag.prerelease == "alpha":
        return "Alpha"
    if tag.prerelease == "beta":
        return "Beta"
    if tag.prerelease == "rc":
        return "Release Candidate"
    return "Stable"


def determine_version(
    reachable_tag_names: Iterable[str],
    exact_tag_names: Iterable[str],
    distances: Mapping[str, int],
    commit_hash: str,
    dirty: bool,
) -> VersionResult:
    """Select version metadata from already-collected repository facts."""
    tags = [tag for name in reachable_tag_names if (tag := parse_semver_tag(name))]
    exact_names = set(exact_tag_names)
    exact_tags = [tag for tag in tags if tag.name in exact_names]
    warnings: list[str] = []

    major_lines = sorted({tag.major for tag in tags})
    if len(major_lines) > 1:
        warnings.append(
            "Multiple reachable major release lines detected: "
            + ", ".join(f"v{major}.x" for major in major_lines)
        )

    selected: SemanticTag | None = None
    distance = 0
    if exact_tags:
        selected = max(exact_tags, key=lambda tag: tag.sort_key)
    elif tags:
        nearest_distance = min(distances[tag.name] for tag in tags)
        nearest = [tag for tag in tags if distances[tag.name] == nearest_distance]
        selected = max(nearest, key=lambda tag: tag.sort_key)
        distance = nearest_distance

    if selected is None:
        version = f"0.0.0+g{commit_hash}"
        if dirty:
            version += ".dirty"
        return VersionResult(version, "Development", None, tuple(warnings))

    if distance or dirty:
        if distance:
            version = f"{selected.version}+{distance}.g{commit_hash}"
        else:
            version = f"{selected.version}+0.g{commit_hash}.dirty"
        if dirty and distance:
            version += ".dirty"
        return VersionResult(version, "Development", selected.name, tuple(warnings))

    return VersionResult(
        selected.version,
        release_type(selected),
        selected.name,
        tuple(warnings),
    )


def run_git(arguments: Sequence[str], *, check: bool = True) -> str:
    """Run a Git command in the project repository and return stdout."""
    try:
        process = subprocess.run(
            ["git", *arguments],
            cwd=PROJECT_ROOT,
            check=check,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise GitUnavailableError("Git is not installed or is not on PATH") from error
    except subprocess.CalledProcessError as error:
        message = error.stderr.strip() or error.stdout.strip() or str(error)
        raise RuntimeError(f"Git command failed: {message}") from error
    return process.stdout.strip()


def inspect_repository() -> VersionResult:
    """Collect Git facts and select the current build version."""
    try:
        inside_repository = run_git(["rev-parse", "--is-inside-work-tree"])
    except RuntimeError as error:
        raise GitUnavailableError("Current folder is not a Git repository") from error
    if inside_repository != "true":
        raise GitUnavailableError("Current folder is not a Git repository")

    commit_hash = run_git(["rev-parse", "--short=7", "HEAD"])
    branch = run_git(["branch", "--show-current"]) or UNKNOWN
    commit_timestamp = int(run_git(["show", "-s", "--format=%ct", "HEAD"]))
    reachable_names = run_git(["tag", "--merged", "HEAD", "--list"]).splitlines()
    exact_names = run_git(["tag", "--points-at", "HEAD", "--list"]).splitlines()
    valid_names = [name for name in reachable_names if parse_semver_tag(name)]
    distances = {
        name: int(run_git(["rev-list", "--count", f"{name}..HEAD"]))
        for name in valid_names
    }
    dirty = bool(run_git(["status", "--porcelain", "--untracked-files=normal"]))
    result = determine_version(
        reachable_names,
        exact_names,
        distances,
        commit_hash,
        dirty,
    )
    return VersionResult(
        result.version,
        result.release,
        result.selected_tag,
        result.warnings,
        commit_hash,
        branch,
        commit_timestamp,
    )


def render_build_metadata(
    version: str,
    release: str,
    git_commit: str = UNKNOWN,
    git_branch: str = UNKNOWN,
    build_date: str = UNKNOWN,
) -> str:
    """Render the importable, build-only metadata module."""
    return f'''"""Generated build metadata; do not edit or commit this file."""

APP_VERSION = {version!r}
APP_RELEASE = {release!r}
APP_GIT_COMMIT = {git_commit!r}
APP_GIT_BRANCH = {git_branch!r}
APP_BUILD_DATE = {build_date!r}
'''


def write_build_metadata(
    version: str,
    release: str,
    git_commit: str = UNKNOWN,
    git_branch: str = UNKNOWN,
    build_date: str = UNKNOWN,
) -> None:
    """Atomically write Git-ignored build metadata as UTF-8."""
    BUILD_METADATA_MODULE.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=BUILD_METADATA_MODULE.parent,
            prefix=f".{BUILD_METADATA_MODULE.name}.",
            delete=False,
        ) as temporary_file:
            temporary_file.write(
                render_build_metadata(
                    version, release, git_commit, git_branch, build_date
                )
            )
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, BUILD_METADATA_MODULE)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def existing_fallback() -> tuple[str, str]:
    """Read committed fallback constants without importing generated metadata."""
    try:
        tree = ast.parse(STATIC_VERSION_MODULE.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return FALLBACK_VERSION, FALLBACK_RELEASE
    values: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Name)
            and target.id in {"APP_VERSION", "APP_RELEASE"}
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            values[target.id] = node.value.value
    return (
        values.get("APP_VERSION", FALLBACK_VERSION),
        values.get("APP_RELEASE", FALLBACK_RELEASE),
    )


def determine_build_date(result: VersionResult) -> str:
    """Return a reproducible UTC date whenever build inputs provide one."""
    source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if source_date_epoch is not None:
        try:
            timestamp = int(source_date_epoch)
        except ValueError as error:
            raise ValueError("SOURCE_DATE_EPOCH must be an integer timestamp") from error
    elif result.commit_timestamp is not None:
        timestamp = result.commit_timestamp
    else:
        timestamp = int(datetime.now(timezone.utc).timestamp())
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def main() -> int:
    """Detect, report, and persist the build version."""
    try:
        result = inspect_repository()
    except GitUnavailableError as error:
        version, release = existing_fallback()
        print(f"Warning: {error}; using committed fallback {version}.", file=sys.stderr)
        result = VersionResult(version, release, None)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Version generation failed: {error}", file=sys.stderr)
        return 1

    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    selected = result.selected_tag or "no valid reachable tag"
    print(f"Selected Git tag: {selected}")
    print(f"Detected application version: {result.version}")
    print(f"Detected release type: {result.release}")
    try:
        build_date = determine_build_date(result)
    except (OSError, OverflowError, ValueError) as error:
        print(f"Version generation failed: {error}", file=sys.stderr)
        return 1
    print(f"Detected Git commit: {result.git_commit}")
    print(f"Detected Git branch: {result.git_branch}")
    print(f"Build date: {build_date}")
    try:
        write_build_metadata(
            result.version,
            result.release,
            result.git_commit,
            result.git_branch,
            build_date,
        )
    except OSError as error:
        print(
            f"Version generation failed while writing {BUILD_METADATA_MODULE}: {error}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
