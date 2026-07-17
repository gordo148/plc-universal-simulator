# PLC Universal Simulator — Code Metrics Tables

## 1. Scope and method

This appendix records the quantitative baseline collected before Feedback Engine V2. Metrics were obtained without running the application or a build. Python files were parsed with the standard-library AST; physical lines were counted directly. Generated trees (`build/`, `dist/`), virtual environments and `.git/` were excluded. Numbers are descriptive, not a substitute for runtime profiling.

| Item | Value |
|---|---:|
| Tracked repository files | 132 |
| Python files assessed | 88 |
| Markdown files present before this audit | 18 |
| Python physical LOC | 17,842 |
| Python non-blank/non-comment LOC | 14,882 |
| Blank Python lines | 2,921 |
| Comment-only Python lines | 39 |
| Production/support Python LOC (excluding tests) | 12,111 |
| Top-level classes | 60 |
| All function definitions | 1,149 |
| Module/nested functions | 773 |
| Methods, including nested classes | 376 |
| Import statements | 511 |
| Branch decision points | 1,916 |
| Loops and comprehensions | 581 |
| `try` blocks | 124 |
| `with` blocks | 33 |
| Lambdas | 440 |
| Assertions | 824 |
| Static `test_*` definitions | 295 |
| Distinct metric dimensions collected | 52 |

### Tooling availability

`radon`, `ruff`, `vulture` and `pylint` were not installed in the inspected environment. Complexity and dependency results below therefore use a documented AST approximation. No formatter, build, test suite or application process was run during this audit.

## 2. Metrics by area

| Area | Files | Physical LOC | Logical LOC | Classes | Module functions | Direct methods | Imports |
|---|---:|---:|---:|---:|---:|---:|---:|
| `core/` | 8 | 537 | 448 | 6 | 19 | 17 | 16 |
| `ui/` | 16 | 8,623 | 7,369 | 6 | 316 | 97 | 171 |
| `services/` | 6 | 1,066 | 937 | 3 | 16 | 31 | 27 |
| `drivers/` | 7 | 602 | 487 | 8 | 4 | 48 | 16 |
| `tests/` | 41 | 5,731 | 4,543 | 33 | 326 | 120 | 184 |
| `scripts/` | 8 | 1,179 | 1,009 | 4 | 37 | 5 | 84 |
| `plugins/` | 1 | 4 | 3 | 0 | 0 | 0 | 0 |
| `main.py` | 1 | 100 | 86 | 0 | 3 | 0 | 13 |

The UI contains 48.3% of all Python LOC and most orchestration logic. Tests represent 32.1% of Python LOC, a positive signal, although LOC is not coverage.

## 3. Largest modules

| Rank | Module | Physical LOC | Logical LOC | Architectural observation |
|---:|---|---:|---:|---|
| 1 | `ui/tag_manager.py` | 1,951 | 1,664 | UI, address policy, CSV parsing and import orchestration coexist. |
| 2 | `ui/main_window.py` | 1,259 | 1,092 | Application composition, lifecycle, scheduling and runtime state converge. |
| 3 | `ui/project_config.py` | 990 | 882 | Strong staging/rollback, but persistence remains UI-aware. |
| 4 | `services/plc_service.py` | 770 | 693 | Protocol dispatch, caching, conversion and scanning share one service. |
| 5 | `ui/analog_tab.py` | 764 | — | Large table/controller module with incremental-refresh logic. |
| 6 | `ui/dashboard_tab.py` | 750 | — | Dashboard presentation, filters, sorting and scheduling are coupled. |
| 7 | `ui/header.py` | 514 | — | Header construction and live status updates coexist. |
| 8 | `ui/digital_tab.py` | 502 | — | Mirrors analog responsibilities with repeated patterns. |
| 9 | `ui/analog_profiles.py` | 452 | — | Profile validation and presentation support. |
| 10 | `ui/trend_tab.py` | 431 | — | Sampling controls and chart rendering are tightly connected. |
| 11 | `ui/alarm_tab.py` | 337 | — | Alarm evaluation, state and row widgets share a module. |
| 12 | `core/dashboard_model.py` | 290 | — | Useful pure filtering/sorting boundary. |

## 4. Largest classes

Class LOC extends from its declaration to the last member; aggregate complexity is the sum of contained callable complexity.

| Class | Location | LOC | Methods | Aggregate complexity | Maximum nesting |
|---|---|---:|---:|---:|---:|
| `PLCSimulator` | `ui/main_window.py:142` | 1,118 | 71 | 199 | 9 |
| `PLCService` | `services/plc_service.py:53` | 619 | 22 | 136 | 10 |
| `AnalogSimulationManager` | `services/analog_simulation.py:168` | 200 | 16 | 43 | — |
| `SchneiderDriver` | `drivers/schneider.py` | 133 | 9 | 26 | — |
| `ApplicationSettings` | `core/settings.py` | 117 | 5 | 31 | — |
| `SafeScrollableFrame` | `ui/scrollable.py` | 101 | 7 | 18 | — |
| `OmronDriver` | `drivers/omron.py` | 100 | 12 | 20 | — |
| `RuntimeCache` | `core/tag_runtime.py` | 99 | 11 | 11 | — |
| `SiemensDriver` | `drivers/siemens.py` | 70 | 9 | 12 | — |
| `InternalSimulatorDriver` | `drivers/internal.py` | 63 | 10 | 8 | — |
| `RockwellDriver` | `drivers/rockwell.py` | 38 | 6 | 12 | — |
| `Plugin` | `core/plugin_loader.py` | 31 | 4 | 4 | — |

## 5. Function size and complexity

The complexity score is a McCabe-style approximation: one base path plus AST decision constructs. It is suitable for ranking hotspots, not for comparison with a differently configured external tool.

### Distribution

| Band | Approximate complexity | Functions | Share |
|---|---:|---:|---:|
| A | 1–5 | 985 | 85.7% |
| B | 6–10 | 105 | 9.1% |
| C | 11–20 | 45 | 3.9% |
| D | 21–30 | 10 | 0.9% |
| E | 31–40 | 3 | 0.3% |
| F | >40 | 1 | 0.1% |
| **Total** |  | **1,149** | **100%** |

Mean complexity is 3.25, median 2 and maximum 46. The overall distribution is healthy, but high-complexity functions sit on critical UI/runtime paths.

### Complexity hotspots

| Function | Location | Complexity | LOC | Branches | Loops | Max nesting | Parameters |
|---|---|---:|---:|---:|---:|---:|---:|
| `refresh_dashboard_table` | `ui/dashboard_tab.py:500` | 46 | 65 | 35 | 10 | 5 | 1 |
| `refresh_analog_visible_rows` | `ui/analog_tab.py:245` | 31 | 107 | 25 | 5 | 2 | 2 |
| `read_tags_csv` | `ui/tag_manager.py:984` | 31 | 107 | 22 | 8 | 5 | 2 |
| `suggest_address` | `ui/tag_manager.py:772` | 31 | 73 | 18 | 12 | 6 | 4 |
| `build_project_data` | `ui/project_config.py:139` | 30 | 152 | 22 | 7 | 4 | 1 |
| `_stage_project_data` | `ui/project_config.py:737` | 30 | 103 | 23 | 6 | 4 | 1 |
| `refresh_digital_visible_rows` | `ui/digital_tab.py:262` | 28 | 95 | 22 | 5 | 2 | 2 |
| `_restore_analog_profiles` | `ui/project_config.py:560` | 26 | 67 | 18 | 7 | 4 | 2 |
| `update_dashboard` | `ui/dashboard_tab.py:674` | 26 | 18 | 20 | 5 | 2 | 2 |
| `apply_imported_tags` | `ui/tag_manager.py:1440` | 24 | 122 | 22 | 1 | 3 | 5 |
| `read_tia_tags_csv` | `ui/tag_manager.py:1117` | 24 | 98 | — | — | — | — |
| `normalize_analog_profile` | `ui/analog_profiles.py:24` | 22 | 84 | — | — | — | — |
| `_apply_project_data` | `ui/project_config.py:338` | 21 | 104 | — | — | 7 | — |
| `_scan_siemens` | `services/plc_service.py:373` | 20 | 89 | — | — | 10 | — |
| `_write_numeric_impl` | `services/plc_service.py:278` | 20 | 67 | — | — | — | — |
| `migrate_project_data` | `ui/project_config.py:855` | 20 | 55 | — | — | — | — |

### Longest functions

| Function | Location | LOC | Complexity | Main concern |
|---|---|---:|---:|---|
| `create_tag_manager_tab` | `ui/tag_manager.py:107` | 230 | 9 | Construction and behavior wiring are monolithic. |
| `build_project_data` | `ui/project_config.py:139` | 152 | 30 | Serialization policy and UI extraction are coupled. |
| `on_close` | `ui/main_window.py` | 143 | 16 | Shutdown coordinates many unrelated resources. |
| `create_dashboard_tab` | `ui/dashboard_tab.py` | 133 | 14 | Layout, widget state and callbacks are assembled together. |
| `create_trend_tab` | `ui/trend_tab.py` | 132 | 16 | Chart, controls and sampling state are coupled. |
| `create_header` | `ui/header.py` | 122 | 1 | Primarily declarative, but difficult to reuse/test. |
| `apply_imported_tags` | `ui/tag_manager.py:1440` | 122 | 24 | Validation, mutation and UI effects share a transaction. |
| `refresh_analog_visible_rows` | `ui/analog_tab.py:245` | 107 | 31 | Complex incremental reconciliation. |
| `read_tags_csv` | `ui/tag_manager.py:984` | 107 | 31 | Format detection, parsing and validation coexist. |
| `_apply_project_data` | `ui/project_config.py:338` | 104 | 21 | Deeply nested restoration flow. |
| `_stage_project_data` | `ui/project_config.py:737` | 103 | 30 | Validation/migration staging has many branches. |
| `create_pid_tab` | `ui/pid_tab.py` | 100 | 4 | Large widget constructor. |

## 6. Import and dependency metrics

### Internal fan-out

| Module | Internal modules imported |
|---|---:|
| `ui.main_window` | 19 |
| `ui.project_config` | 12 |
| `ui.dashboard_tab` | 8 |
| `ui.tag_manager` | 7 |
| `ui.analog_tab` | 7 |
| `main` | 6 |
| `ui.alarm_tab` | 5 |
| `ui.digital_tab` | 5 |

### Internal fan-in

| Module | Internal importers |
|---|---:|
| `core.tag_model` | 31 |
| `core.tag_runtime` | 21 |
| `ui.tag_manager` | 15 |
| `ui.table_utils` | 10 |
| `services.plc_service` | 10 |
| `ui.scrollable` | 9 |
| `core.connection_state` | 8 |
| `ui.main_window` | 8 |
| `ui.analog_profiles` | 7 |
| `ui.header` | 7 |
| `ui.project_config` | 7 |
| `core.version` | 6 |

### Cyclic dependencies

One multi-module strongly connected component was found:

```text
ui.alarm_tab
  ↕
ui.analog_tab ↔ ui.dashboard_tab ↔ ui.digital_tab
  ↕                         ↕
ui.project_config ↔ ui.tag_manager
```

The cycle is enabled by cross-imported callbacks and shared mutable application state. It increases import-order sensitivity and makes isolated tests harder.

### Declared third-party dependencies

| Dependency | Role | Constraint quality |
|---|---|---|
| `customtkinter` | Main UI toolkit | Unpinned |
| `python-snap7` | Siemens S7 | Unpinned |
| `pymodbus` | Modbus | Unpinned |
| `pycomm3` | Rockwell | Unpinned |
| `fins-driver` | Omron | Unpinned |
| `matplotlib` | Trends | Unpinned |
| `pillow` | Images/assets | Unpinned |
| `pyinstaller` | Packaging | Unpinned |
| `pytest` | Tests | Unpinned |

Direct import scanning also found `tkinter`, `PIL`, `snap7`, `pymodbus`, `pycomm3`, `fins` and `matplotlib`. Dependency reproducibility is limited without locks or bounded versions.

## 7. Runtime and performance indicators

| Area | Current pattern | Complexity/pressure | Priority |
|---|---|---|---|
| PLC cyclic read | Scheduled through Tk callback; protocol work can execute on UI thread | Network latency can freeze all widgets | Critical |
| Runtime cache | Reconciled with tag population on refresh | Repeated O(n) scans | High |
| Dashboard | Incremental cell writes, but population/filter/sort scans remain | O(n) or O(n log n) per relevant refresh | Medium |
| Digital/Analog | Incremental visible-row reconciliation | Good direction; controller branches are complex | Medium |
| Feedbacks | Per-row widgets plus 500 ms scans | Widget count and duplicate polling scale poorly | High |
| Alarms | Per-item widgets plus 500 ms scans | Linear scan and widget overhead | High |
| Trends | Full chart redraw on refresh/sample | Rendering cost grows with series and history | High |
| Tag Manager | Table rebuilds and validation scans | Large imports can block UI | High |
| Project load | Staged, validated and rollback-capable | Safer, but UI thread may process large files | Medium |
| CSV import | Whole-file byte load and format probing | Memory spike; no explicit size guard | High |

No definitive product O(n²) defect was proven statically. The more immediate scaling concern is several independent O(n) pollers over the same tag population, which aggregate into redundant work and repeated widget updates.

## 8. Test metrics

| Metric | Result |
|---|---:|
| Test files | 41 |
| Static `test_*` definitions | 295 |
| Assertions in all Python code | 824 |
| Last previously verified repository baseline | 460 passed |
| Tests executed during this audit | 0 |
| Instrumented coverage | Unknown |
| Coverage configuration found | None |
| CI workflow found | None |

### Qualitative coverage matrix

| Area | Relative strength | Important gaps |
|---|---|---|
| Tag model/runtime | Strong | Soak behavior and concurrent updates |
| Dashboard | Strong unit/regression focus | Real Tk lifecycle and long-running load |
| Project persistence | Strong | Corrupt/very large/adversarial projects |
| CSV | Moderate/strong | Size limits, encoding corpus, fuzzing |
| Drivers | Moderate | Hardware-in-loop, disconnect races, vendor matrices |
| Feedbacks | Weak/moderate | Deterministic engine semantics and scale |
| Alarms | Weak/moderate | Quality-state semantics, acknowledgement/history |
| Trends | Moderate | Memory bounds, long soak, rendering performance |
| Packaging | Moderate scripts/tests | Windows and installed binary automation |
| Security | Weak | Malicious project/CSV/plugin inputs |

## 9. Static hygiene indicators

| Indicator | Result | Interpretation |
|---|---|---|
| Exact normalized duplicate function bodies | None found | Does not exclude near-duplicate UI patterns. |
| Confirmed dead public APIs | None established | Dynamic callbacks and monkeypatch seams create false positives. |
| Heuristic unused constant | `SOURCE_BUILD_TYPE` in `scripts/generate_version.py:18` | Verify before removal. |
| Unused-import confidence | Low without Ruff/Pyflakes | Do not remove from heuristic results alone. |
| Circular imports | One six-module UI SCC | Confirmed architectural debt. |
| Functions above complexity 20 | 14 | Concentrated in UI, persistence and PLC scan paths. |
| Classes above 500 LOC | 2 | `PLCSimulator`, `PLCService`. |
| Modules above 1,000 LOC | 2 | `tag_manager`, `main_window`. |

## 10. Architecture scorecard

| Dimension | Score / 10 | Evidence summary |
|---|---:|---|
| Architecture | 6.4 | Clear folders and useful models, but UI is the composition/runtime hub. |
| Organization | 6.5 | Recognizable domains; several oversized modules. |
| Scalability | 5.2 | Independent polling and per-item widgets limit large projects. |
| Performance | 5.8 | Incremental Dashboard work is good; PLC/UI coupling remains critical. |
| Modularity | 5.7 | Drivers exist as modules, but orchestration is cross-cutting. |
| Testability | 6.8 | Broad test corpus; global app state and Tk callbacks impede isolation. |
| Documentation | 8.2 | Extensive design and operational documentation. |
| UX architecture | 7.0 | Rich desktop workflow; consistency and responsiveness risks remain. |
| Maintainability | 6.0 | Local quality is often good; hotspot concentration raises change cost. |
| Feedback Engine V2 readiness | 5.0 | Requires event/runtime boundary and stable identity first. |
| SOLID | 5.6 | SRP and DIP are weakest around `PLCSimulator`/`PLCService`. |
| DRY | 5.8 | Analog/digital/table/poller patterns repeat structurally. |
| KISS | 6.4 | Direct design is understandable, but central orchestration is complex. |
| Separation of concerns | 5.5 | UI, persistence and runtime responsibilities frequently meet. |
| Encapsulation | 5.7 | Mutable app attributes serve as a de facto service locator. |
| Composition over inheritance | 7.2 | Composition is common; boundaries need formal interfaces. |

## 11. Metric limitations

- Complexity is an AST approximation and excludes runtime dispatch complexity.
- Dynamic imports, Tk callback registration and test monkeypatching prevent reliable dead-code claims without execution-aware analysis.
- LOC and test counts do not measure correctness or behavioral coverage.
- Performance impacts are architectural estimates; they require profiling at 1,000, 2,000 and 5,000 tags.
- Hardware-driver behavior requires vendor devices or protocol simulators.
- Existing untracked `docs/SOFTWARE_ARCHITECTURE_REVIEW.md` predates this audit and was not modified.
