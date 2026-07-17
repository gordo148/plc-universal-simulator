# Dashboard v2 — Implementation Plan

## Baseline and scope

This plan treats the five SDS volumes as one specification and follows
`docs/IMPLEMENTATION_RULES.md`. The recorded pre-implementation baseline is
435 passing tests (`pytest -q`, 2026-07-17). The worktree already contains
uncommitted Siemens, comments, CSV/config-path, Dashboard and settings work;
those changes are preserved.

No application version, release metadata, installer semantics, project schema,
driver protocol behaviour, Git history or remote state will be changed.

## Current architecture

- `ui/main_window.py` owns the Tk root, tracked `after()` scheduling, tab
  lifecycle, project actions, runtime polling and application settings writes.
- `ui/dashboard_tab.py` creates the Dashboard and currently combines view
  construction, filtering, sorting, row reconciliation, details, cards, events
  and navigation. It refreshes every 750 ms through the tracked scheduler.
- Dashboard rows are `ttk.Treeview` items. The current incremental path keeps
  `_dashboard_row_ids`, `_dashboard_row_values` and `_dashboard_row_order`, so
  unchanged rows are not deleted/reinserted or reconfigured.
- `core/tag_model.py` defines configuration-only `TagDefinition`. It has no
  persistent ID; names are validated unique by current import/project paths.
- `core/tag_runtime.py` owns effective value, validity, source and timestamp,
  keyed by tag name. Dashboard identity therefore remains project-scoped name,
  isolated behind mapping helpers; a schema migration is deliberately avoided.
- `services/settings_service.py` provides JSON user settings with atomic
  temporary-file replacement. A partial Dashboard preference draft exists in
  the interrupted worktree and must be completed/migrated rather than discarded.
- `ui/project_config.py` serializes `.simproject` definitions and feature flags.
  Dashboard presentation preferences are absent and will remain absent.
- `ui/table_utils.py` provides search, sorting, debounce, keyboard navigation,
  copy and one lightweight dynamic tooltip per table.
- `ui/tag_manager.py` owns tag CRUD, CSV, compatibility filtering and the
  dashboard-eligible population (`enabled_dashboard` and brand-compatible).
- `ui/trend_tab.py`, `ui/alarm_tab.py`, `ui/feedback_tab.py`, Digital/Analog and
  PID consume the same definitions/runtime cache. Dashboard navigation must use
  their existing tab/search/selection flows through thin adapters.
- `services/plc_service.py` and `drivers/*` own Siemens, Schneider and other PLC
  communications. Dashboard v2 will not change these modules.
- Packaging is PyInstaller one-folder. Tests are headless; graphical/manual
  validation uses the available Linux display when possible.

## Requirement-to-component mapping and gap analysis

| SDS area | Current state | Planned component/change |
| --- | --- | --- |
| VIS/USR/UX layout | Fixed left/right packed frames; useful but dense | `dashboard_tab.py`: adjustable persisted split, compact controls, required cards and accessible text |
| UXT/COL column registry | Tuple, widths and sortable set are scattered | New `ui/dashboard_model.py`: authoritative immutable registry, labels, bounds, defaults and formatting metadata |
| UXC/COLI columns | Resizable and horizontal scroll exist; no visibility/order/auto-fit | `dashboard_tab.py` + model helpers: validated `displaycolumns`, Columns menu, deterministic Move Left/Right, bounded Auto Fit, debounced final width persistence |
| UXM Compact View | Missing | Versioned settings state with exact previous Full layout; apply only `displaycolumns`/widths, never rebuild rows |
| UXF/FLT search and filters | Search already covers name/address/comment/type; single mutually-exclusive quick filter | Pure filter-state helpers and composable GOOD/BAD/feature/type toggles; persisted, immediate menu toggles, explicit no-results overlay |
| UXO/SORT sorting | Five columns sortable; indicator/persistence absent; mixed values fragile | Pure type-aware sort keys, one-arrow heading labels, persisted direction; stable/throttled dynamic sort policy |
| UXS/SEL Selected Tag | All requested values exist in flat labels; full refresh every cycle | Structured General/Values/Configuration/Diagnostics groups; cached static and dynamic update paths; safe empty/hidden state |
| UXN/NAV context/navigation | Tooltip and BOOL/analog double-click exist; no Dashboard context menu | Stable mapping-based copy actions, Locate in Tag Manager, Open in Trends; preserve existing double-click behaviour |
| UXH/STAT statistics | Many summary cards, but no explicit GOOD/BAD operational set | Total/GOOD/BAD/Simulation/Trend/Alarm semantics over all eligible Dashboard tags plus Showing visible/total |
| LIFE/DATA/REND lifecycle | Scheduled cancellation and incremental snapshots exist; project generation absent | Reset mappings/selection on project transition; generation token/structure signature; guard destroyed widgets; retain viewport |
| PREF/PST settings | Atomic settings exists; Dashboard draft is unversioned/incomplete | Complete a versioned validated `dashboard_ui` section with partial-field recovery and legacy draft migration; never touch project data |
| PERF | Existing 1,000-tag Dashboard measurements; update scans current population | Preserve no-per-row-widget design, cap auto-fit samples, compare snapshots, measure 50/1,000/5,000 operations |
| ERR/EDGE | Empty state works; malformed fields can raise; details can remain stale | Safe access/format helpers, explicit empty/no-match states, local logging, no broad error swallowing |
| CMP/SCP | Drivers/project/CSV separated | Regression-only validation; no driver, simulation, CSV schema or project schema changes |

## Files

### Create

- `ui/dashboard_model.py` — registry, validated preferences, filter/sort,
  statistics and formatting helpers without Tk/application construction.
- `tests/test_dashboard_v2.py` — focused unit/helper/incremental interaction and
  performance coverage.
- `scripts/benchmark_dashboard_v2.py` — reproducible 50/1,000/5,000 non-PLC
  measurement harness if the existing benchmark cannot express required cases.
- `docs/Dashboard_v2_SDS/IMPLEMENTATION_DECISIONS.md`.
- `docs/Dashboard_v2_SDS/IMPLEMENTATION_STATUS.md`.
- `docs/Dashboard_v2_SDS/MANUAL_VALIDATION_CHECKLIST.md`.
- `docs/Dashboard_v2_SDS/IMPLEMENTATION_REPORT.md` at handoff.

### Modify

- `ui/dashboard_tab.py` — view/controller integration, controls, splitter,
  details, context actions, lifecycle and incremental rendering.
- `services/settings_service.py` — versioned Dashboard preference validation,
  migration and platform-writable packaged path compatibility.
- `ui/main_window.py` — only if needed for safe debounced preference flush or
  Dashboard lifecycle adapter.
- `ui/project_config.py` — only a thin project-generation/reset notification if
  lifecycle tests prove it necessary; no serialized format changes.
- `tests/test_dashboard_overview.py`, `tests/test_user_settings.py`, and project
  compatibility tests for existing public behaviour.
- `docs/DASHBOARD.md` to document final architecture and measured semantics.

### Remove

None planned. Existing APIs and files remain available.

## Dependencies and implementation phases

### Phase 1 — foundation and registry

1. Introduce registry and versioned preference schema/migration.
2. Validate unknown/duplicate/missing keys, force Name visible, clamp widths,
   validate sort/filter/splitter state and preserve valid sibling fields.
3. Retain callable-only heading configuration and add sort indicators.
4. Add pure type-aware search/filter/sort/statistics helpers.
5. Focused tests, settings/project serialization regressions, diff review.

### Phase 2 — columns, splitter and Compact View

1. Apply visible ordered columns through `displaycolumns` only.
2. Columns menu: toggles, Name protection, Move Left/Right, Auto Fit selected,
   Auto Fit visible, Restore Previous Layout and Restore Defaults.
3. Compact View captures/restores exact Full layout and persists externally.
4. Capture final separator widths and splitter position with debounced saves.
5. Verify rows, selection and viewport remain unchanged.

### Phase 3 — interaction and inspector

1. Composable filter menu and search shortcuts (`Ctrl+F`, `Escape`).
2. Explicit no-project/no-tags/no-results states.
3. Separate static/dynamic Selected Tag updates and grouped presentation.
4. Stable context menu copy/navigation and keyboard navigation.
5. Unicode/long/zero/False/missing-field and navigation tests.

### Phase 4 — statistics, lifecycle and performance

1. Required operational statistics and documented total-population semantics.
2. Project-scoped mapping reset/generation guard and stale callback tests.
3. Preserve selection/focus/yview through structural transformations.
4. Measure population/search/filter/sort/update at 50, 1,000 and 5,000 tags.
5. Full regression, compileall, diff check and available graphical smoke tests.

### Phase 5 — verification and handoff

1. Review every normative ID against implementation/tests/manual checklist.
2. Complete status, decisions, manual checklist and final report.
3. Confirm version/release files unchanged and no commit/push.

## Technical and regression risks

- **Identity:** name is the only stable runtime key. Project-switch generation
  prevents same-name stale selection; rename limitations are documented.
- **Tk portability:** header drag is not reliably portable. Deterministic menu
  Move Left/Right is used per SDS fallback; it is keyboard/mouse accessible.
- **Dynamic sorting:** Value sorting can cause row movement. Automatic resort is
  limited to the existing 750 ms coalesced Dashboard cycle and only moves rows
  when the computed order changes; this policy will be measured/documented.
- **Disk write frequency:** resize/split changes persist only on release through
  a debounce, with shutdown flush and atomic settings writer.
- **Preference compatibility:** the partial unversioned draft and older settings
  must migrate field-by-field. Invalid layout never blocks startup.
- **Project dirty state:** presentation handlers only update settings and must
  never call project dirty markers; explicit tests compare project snapshots.
- **Performance:** no per-tag widgets, unbounded auto-fit scan, full delete/insert
  or unchanged `item()` writes will be introduced.
- **Cross-module navigation:** adapters must respect lazy tab creation and
  current selection mechanisms without changing Trends/Tag Manager APIs.
- **Worktree overlap:** edits are limited to named files and reviewed after each
  phase so unrelated Siemens/comment/config-path work remains intact.

## Compatibility strategy

- Keep `.simproject` schema/version and project serialization unchanged.
- Extend the existing atomic user settings JSON with migration and defaults.
- Keep old settings loadable; retain recent projects/configs paths unchanged.
- Use generic `TagDefinition`/`RuntimeTagCache` data, never driver branches, so
  Siemens/Schneider/other supported tags follow the current compatibility gate.
- Reuse current CSV comment fields, tooltip helper, alarm/trend/simulation flags
  and runtime values; do not duplicate their engines.
- Preserve existing Dashboard public entry points (`create_dashboard_tab`,
  `update_dashboard`, `refresh_dashboard`, cancellation/event helpers).

## Test strategy

- Phase 1: registry/default/migration/corruption, heading callback, numeric sort,
  Unicode search, filter matrix, statistic semantics, project serialization.
- Phase 2: show/hide/order/width clamps, Name protection, compact round-trip,
  displaycolumns without row mutation, auto-fit cap/work bound, debounce.
- Phase 3: empty state matrix, zero/False, selected static/dynamic update counts,
  selection identity, context copy/navigation, shortcuts and malformed tags.
- Phase 4: unchanged-cell suppression, one-row update, yview/selection retention,
  project generation, callback cancellation and 50/1,000/5,000 measurements.
- Regression: complete pytest after each major phase where practical; focused
  Dashboard/settings/project tests after every phase; final `pytest`,
  `python -m compileall .`, available lint (none configured), migration/driver/
  CSV tests and `git diff --check`.

## Definition of Done

- Every applicable normative requirement is implemented or explicitly mapped
  to a documented reliable fallback/manual check.
- All automated tests pass; compilation and whitespace checks pass.
- Dashboard starts in no-project, empty and populated states without Tcl errors.
- Routine live updates demonstrably avoid full Treeview reconstruction and
  preserve user context.
- Preferences are versioned, validated, atomic, external to projects and persist
  across restart/project changes.
- Existing projects, drivers, simulations, CSV, Feedbacks, Trends and Alarm
  behaviour remain compatible.
- Measured large-fixture results and honest manual limitations are recorded.
- Version/release metadata and Git history/remotes are unchanged.

## Cross-volume review

The plan was reviewed after reading Volumes 1–5 together. It covers product
scope and compatibility (Volume 1), all interaction groups and accessibility
(Volume 2), lifecycle/functional/edge behaviour (Volume 3), component and
incremental-performance boundaries (Volume 4), and phased verification,
traceability, manual checklist and handoff artefacts (Volume 5).
