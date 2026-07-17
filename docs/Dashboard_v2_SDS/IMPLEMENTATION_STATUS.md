# Dashboard v2 — Implementation Status

## Phase 0 — Discovery and baseline

- **State:** Complete
- **Files changed:** planning/status/decision documents only. Pre-existing
  worktree changes were inspected and preserved.
- **Requirements addressed:** EXEC-001, PH0-001..003, ARCH-001..002, RSK-001,
  ACC-002, CHK-001.
- **Tests:** `pytest -q`.
- **Result:** 435 passed in 1.90 s.
- **Problems:** SDS volumes are DOCX; their `word/document.xml` was extracted to
  stdout for complete reading without changing the source documents.
- **Decisions:** deterministic Move Left/Right fallback; project-scoped name
  identity; total-population statistics semantics.
- **Remaining:** Phases 1–5.

## Phase 1 — Foundation and column registry

- **State:** Complete
- **Files altered:** `core/dashboard_model.py`, `services/settings_service.py`,
  `ui/dashboard_tab.py`, Dashboard/settings tests.
- **Requirements:** PH1-001..003, UXT-001, COL-001, SORT-001..002,
  PREF-001..003, PST-002..003, COMP-001..003.
- **Tests:** focused Dashboard/settings/project suite, then full pytest.
- **Result:** all passing; no `command=None`; malformed and legacy preferences
  recover field-by-field.
- **Problems:** interrupted worktree contained an unversioned preference draft.
- **Decision:** explicit migration into versioned `dashboard_ui`.
- **Remaining:** phases 2–5.

## Phase 2 — Columns, splitter and Compact View

- **State:** Complete
- **Files altered:** `core/dashboard_model.py`, `ui/dashboard_tab.py`, tests.
- **Requirements:** UXL-001..003, UXC-001..004, UXM-001..003,
  COL-002..003, COLI-002..003, PH2-001..003.
- **Tests:** displaycolumns row-preservation, Name protection, compact round-trip,
  reorder, width clamp, bounded Auto Fit, preference round-trip.
- **Result:** passing. Column changes never delete rows or mark project dirty.
- **Problems:** native header drag is not portable in ttk.
- **Decision:** SDS-approved deterministic Move Left/Right menu fallback.
- **Remaining:** phases 3–5.

## Phase 3 — Inspector, search, filters and navigation

- **State:** Complete
- **Files altered:** `ui/dashboard_tab.py`, `tests/test_dashboard_v2.py`.
- **Requirements:** UXH-001, UXS-001..003, UXF-001..003, UXN-001..003,
  FLT-001..003, SEL-001..003, NAV-001..003, PH3-001..003.
- **Tests:** Unicode/multi-category filter matrix, no-result state helpers,
  zero value, split static/dynamic details, identity navigation foundations.
- **Result:** passing. One table tooltip/context menu is used; no per-row widget.
- **Problems:** direct alarm configuration API does not exist.
- **Decision:** omit unsupported alarm navigation as required; retain Alarm state.
- **Remaining:** phases 4–5.

## Phase 4 — Statistics, lifecycle and performance

- **State:** Complete
- **Files altered:** `ui/dashboard_tab.py`, `ui/project_config.py`,
  `scripts/benchmark_dashboard_v2.py`, tests and `docs/DASHBOARD.md`.
- **Requirements:** STAT-001..003, DATA-001..003, REND-001..003,
  PERF-001..003, LIFE-001..003, PH4-001..003, QLT-001..003.
- **Tests:** full suite, one-cell/unchanged instrumentation, project mapping
  reset, 5,000-tag bounded test and benchmark.
- **Result:** 451 passing. 5,000-tag model measurements: search 4.585 ms,
  filters 2.083 ms, Value sort 3.792 ms, statistics update 2.018 ms.
- **Problems:** runtime cache exposes no changed-identity stream.
- **Decision:** scan lightweight snapshots but issue Tcl writes only for changed
  cells; Value-sorted row order remains stable until explicit/structural sort.
- **Remaining:** final handoff/manual user validation.

## Phase 5 — Verification and handoff

- **State:** Complete, with real PLC/platform checks delegated
- **Files altered:** SDS plan, decisions, status, checklist and report.
- **Requirements:** TEST-001..003, MAN-001..003, TECH-001..003, HAND-001..003.
- **Tests:** `pytest`; `python -m compileall .`; `git diff --check`; headless
  benchmark; real Tk startup without project; project integration/shutdown.
- **Result:** 451 passed; compileall and diff check passed; graphical startup and
  existing-project lifecycle produced no Dashboard TclError.
- **Problems:** no real Siemens/Schneider PLC and no Windows graphical host.
- **Decisions:** exact remaining checks are in `MANUAL_VALIDATION_CHECKLIST.md`.
- **Remaining:** user acceptance with real imported project/PLC and Windows Tk.
