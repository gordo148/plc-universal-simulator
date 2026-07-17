# Dashboard v2 — Implementation Report

## 1. Summary

Dashboard v2 was implemented incrementally over the existing Treeview/runtime
architecture. It adds a professional, persistent workspace: adjustable split,
validated column registry, visibility/order/width management, bounded Auto Fit,
Compact View, composable filters, persistent sorting with indicators, required
statistics, structured Selected Tag inspector, context actions, empty states,
keyboard shortcuts and cell-level live updates.

No PLC write behaviour, protocol driver, simulation algorithm, CSV schema,
project schema/version, application version or release metadata was changed.

## 2. Final architecture

- `core/dashboard_model.py`: Tk-independent registry, preference schema and
  migration, display layout transforms, bounded sizing, search/filter/sort and
  statistics.
- `services/settings_service.py`: existing atomic writer extended with a
  versioned `dashboard_ui` section and legacy draft migration. Frozen builds use
  an OS user configuration location with read fallback to the legacy adjacent
  settings file.
- `ui/dashboard_tab.py`: widget creation and controller adapters. It applies
  `displaycolumns`, maintains project-scoped name↔item snapshots, updates only
  changed cells, separates static/dynamic details and reuses existing module
  navigation.
- `ui/project_config.py`: one lifecycle notification clears stale Dashboard
  mappings after a new project model is installed; serialization is unchanged.

## 3. Files created and modified

Created:

- `core/dashboard_model.py`
- `tests/test_dashboard_v2.py`
- `scripts/benchmark_dashboard_v2.py`
- SDS implementation plan, decisions, status, checklist and this report

Modified:

- `ui/dashboard_tab.py`
- `ui/project_config.py`
- `services/settings_service.py`
- `tests/test_dashboard_overview.py`
- `tests/test_user_settings.py`
- `docs/DASHBOARD.md`

The five supplied SDS DOCX files and `docs/IMPLEMENTATION_RULES.md` were read and
left unchanged.

## 4. Traceability

| Requirement groups | Implementation | Main evidence | State |
| --- | --- | --- | --- |
| VIS/USR/PRN/QLT | Compact operational layout, explicit text states, incremental UI | Dashboard UI; full regression; manual startup | Complete |
| SCP/CMP/CTX | Preferences external; shared tag/runtime sources; generic driver path | settings/project tests | Complete |
| UXL/UXH | Paned split, minimums, search shortcuts, required cards | Dashboard view/manual screenshot | Complete |
| UXT/UXC/UXM/COL/COLI | Registry, displaycolumns, Move Left/Right, widths, Auto Fit, Compact | `dashboard_model.py`; layout tests | Complete; drag uses fallback |
| UXS/SEL | Grouped scrollable inspector; static/dynamic snapshots; zero/False | selected-detail test | Complete |
| UXF/FLT/FSI | Unicode four-field search and composable status/feature/type filters | filter matrix tests | Complete |
| UXO/SORT | Type-aware sort, missing-last, arrows, persistence, stable live Value order | sort/heading tests | Complete |
| UXN/NAV | Bounded tooltip, copy menu, Tag Manager/Trends adapters | code review/existing navigation regression | Complete |
| STAT | Total-population cards and Showing visible/total | statistic tests | Complete |
| LIFE/DATA/REND/ERR | project reset, tracked callbacks, identity snapshots, changed-cell writes | instrumentation/project tests; graphical shutdown | Complete |
| PREF/PST | version 1 schema, partial recovery, atomic write, packaged user path | settings tests/code review | Complete |
| PERF | 50/1,000/5,000 harness, bounded auto-fit, no per-row widgets | benchmark and performance tests | Complete |
| EXEC/PH/TEST/MAN/HAND | phased records, complete verification and checklist | SDS artefacts | Complete with delegated PLC/Windows checks |

## 5. Architectural decisions

Full rationale is recorded in `IMPLEMENTATION_DECISIONS.md`:

1. ttk header drag was replaced by deterministic Columns → Reorder → Move
   Left/Right, the SDS-approved cross-platform fallback.
2. Existing unique project-scoped tag name remains identity; project generation
   clears mappings rather than introducing a risky project-schema ID.
3. Statistics cards represent the complete compatible dashboard-enabled
   population; Showing represents the filtered population.
4. Value sorting remains stable during routine live cycles and resorts only on
   explicit or structural view changes to prevent continuous row jumping.

## 6. Migration and compatibility

- Missing preferences receive defaults.
- The interrupted unversioned `visible_columns`/`column_order`/width draft is
  migrated to `dashboard_ui` version 1.
- Unknown/duplicate columns are ignored; Name is forced visible; widths and
  splitter are clamped; valid sibling fields survive partial corruption.
- Older `.simproject` files are not migrated or rewritten for Dashboard UI.
- Existing configs/projects, configs/csv, recent-project and last-project logic
  remains untouched by Dashboard v2.
- Siemens, Schneider, other drivers, Trends, Alarmes, Feedbacks and simulations
  continue through their existing shared model/runtime/service paths.

## 7. Verification results

- Baseline: 435 tests passed before Dashboard v2 implementation.
- Final: **451 tests passed in 1.96 s**.
- Focused Dashboard/settings/project tests passed after each phase.
- `python -m compileall .`: passed.
- `git diff --check`: passed.
- No lint/type-check tool is configured in the repository.
- `python main.py` on Linux DISPLAY `:0`: no-project/zero-tag Dashboard opened
  without TclError or unexpected-error dialog.
- Integration launch with `configs/EDPGER02.simproject`: project loaded,
  Dashboard and existing tabs were traversed, Trends started/stopped, and
  tracked shutdown completed without Dashboard callback/Tcl errors.

## 8. Performance

Environment: Fedora Linux, Python 3.14.6, headless pure model harness using
`time.perf_counter`; no PLC/network.

| Tags | Search ms | Filter ms | Value sort ms | Statistics update ms |
| ---: | ---: | ---: | ---: | ---: |
| 50 | 0.165 | 0.074 | 0.050 | 0.027 |
| 1,000 | 0.947 | 0.414 | 3.425 | 0.390 |
| 5,000 | 4.585 | 2.083 | 3.792 | 2.018 |

The UI path has fixed widgets, Auto Fit examines at most 500 visible rows, an
unchanged cycle performs zero row/cell writes, and a changed runtime item uses
`Treeview.set()` only for changed cells. Results exclude compositor and real
driver latency.

## 9. Known limitations/deviations

- Header drag-and-drop is not implemented because ttk has no reliable native
  cross-platform gesture; Move Left/Right provides the complete safe fallback.
- Identity follows the existing unique tag name. Rename is a structural remap;
  there is no persistent tag UUID.
- Direct Alarm configuration navigation is omitted because no stable existing
  API exists; the SDS requires unsupported actions to be omitted/disabled.
- Physical mouse interactions, real PLC quality timing and Windows Tk rendering
  were not fully automatable on this host.

## 10. Manual validation remaining

Use `MANUAL_VALIDATION_CHECKLIST.md`, especially real imported CSV comments,
multi-DB Siemens/PLCSIM, Schneider, 1,000+/5,000 scrolling, column separator
interaction, preference restart, context clipboard/navigation and Windows Tk.

## 11. Residual risks

- Very frequent 5,000-tag polling still scans lightweight runtime snapshots
  because `RuntimeTagCache` has no changed-identity stream; Tcl writes remain
  strictly changed-cell only.
- Theme/font metric differences may produce slightly different Auto Fit widths.
- Existing shutdown of a loaded Trends chart can take several seconds; this is
  pre-existing and outside Dashboard v2.

## 12. Out-of-scope suggestions (not implemented)

- Add immutable tag UUIDs only through a future repository-wide schema/CSV
  migration design.
- Add a runtime-cache change journal if future polling measurements show the
  lightweight snapshot scan is material.
- Validate and tune styling on a dedicated Windows CI graphical runner.
