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
