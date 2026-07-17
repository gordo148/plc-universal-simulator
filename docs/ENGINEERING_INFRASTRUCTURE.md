# Engineering Infrastructure

This document describes the repository checks introduced in Engineering
Infrastructure Phase 1. They change development and CI verification only; they
do not alter simulator runtime behavior or release packaging.

## Supported Python versions

The application supports Python 3.10 or newer. CI verifies the compatibility
floor (3.10) and the current development interpreter generation (3.14).

## Reproducible dependency installation

`requirements.txt` remains the readable list of direct project dependencies.
`constraints.txt` records verified direct versions without changing package
manager or turning the repository into an installable Python package.

```bash
python -m pip install -r requirements.txt -c constraints.txt
```

Matplotlib and its Python-sensitive transitive dependencies use environment
markers because the verified Python 3.10 releases differ from those used with
Python 3.11 and newer. Direct and resolved transitive versions are constrained;
the file should be reviewed deliberately when a dependency is updated.

## Ruff

Ruff is configured in `pyproject.toml` for conservative correctness checks:
syntax errors, invalid Python constructs, undefined names and related obvious
Pyflakes failures. It does not format code, enforce import ordering or report
unused compatibility imports.

```bash
python -m ruff check .
```

## Tests and coverage

The standard headless suite does not require PLC hardware or graphical
interaction. Run it with coverage using:

```bash
python -m pytest \
  --cov \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml
```

Coverage includes the product packages and `main.py`, while excluding tests,
scripts, generated metadata and build output. It reports branch coverage in the
terminal and writes `coverage.xml`. No minimum percentage is enforced in Phase
1; the report establishes a baseline.

## Continuous integration

`.github/workflows/ci.yml` runs for pushes and pull requests. For Python 3.10
and 3.14 it:

1. restores the pip cache keyed by requirements and constraints;
2. installs constrained dependencies;
3. compiles all Python sources;
4. runs Ruff correctness checks;
5. runs the headless pytest suite with coverage;
6. uploads `coverage.xml` as a workflow artifact.

CI intentionally does not build PyInstaller artifacts, access PLC hardware or
perform graphical interaction.

## Architecture Decision Records

The ADR process and naming convention are documented in `docs/adr/README.md`.
Use `docs/adr/ADR_TEMPLATE.md` for future significant decisions. No historical
ADR was created as part of Phase 1.

## Log rotation

Application logs retain their existing location, UTF-8 encoding, timestamps,
format, logger hierarchy and console warning output. The file handler rotates
`plc_simulator.log` when it reaches 5 MiB and retains five backup files, avoiding
unbounded disk growth during long simulator sessions.

Logging initialization is idempotent for the same destination. If the log
directory or file cannot be opened, startup continues with console logging and
emits a warning instead of terminating the application. Rotation limits are
named internal constants; exposing them as user settings is intentionally
deferred to a future phase.

## Defensive input file limits

Files that are loaded completely into memory are checked using filesystem
metadata before parsing. `.simproject` files are limited to 50 MiB and CSV
imports are limited to 25 MiB. The CSV limit applies to generic, Siemens/TIA and
Schneider/vendor imports through their shared byte-reading path.

An oversized file is rejected before JSON parsing, CSV format detection,
migration or application-state mutation. The user receives a clear maximum-size
message, and the log records only the path, detected byte size, category and
configured limit—not file contents. Constants and the small validation helper
are defined in `core/input_limits.py` and are not user-configurable yet.

Row-count, tag-count and cell-length limits remain intentionally deferred; no
repository evidence currently justifies introducing those compatibility-facing
restrictions.

## Stable tag identity in project files

Project schema 4 stores each tag's canonical UUID v4 `tag_id` and persists
Dashboard, Trend, Alarm, PID, digital, analog and optional row-selection
references by that identity. Older project
schemas remain valid: missing IDs are generated during staging, before any
active application state is changed. Opening an older project does not modify
its file; an explicit Save or Save As persists the generated identities.

Malformed and duplicate explicit IDs are rejected before project application.

`RuntimeTagCache` is keyed internally by `tag_id`. Renaming a synchronized tag
preserves its runtime state; replacing it with a new identity does not inherit
state through a reused name or address. Existing name-based calls remain as
transitional compatibility adapters and reject ambiguous names.

Legacy feature names resolve during staging only when unique. Required logical
references reject invalid projects; stale optional selections/configurations are
cleared with diagnostics. Feedbacks currently derive directly from tag direction
and have no separate persisted source/target relationship.

CSV identity and removal of remaining transitional name adapters remain
deferred to later Phase 2A work.
