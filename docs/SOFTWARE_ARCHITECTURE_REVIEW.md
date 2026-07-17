# PLC Universal Simulator — Software Architecture Review

**Document type:** Technical architecture audit  
**Status:** Official project review  
**Scope:** Complete repository architecture prior to Feedback Engine V2  
**Assessment baseline:** Repository state after Dashboard V2 and isolated build-metadata architecture  
**Audience:** Maintainers, technical leads, contributors, release engineers, and future plugin/API developers

---

## Table of Contents

1. [Purpose and Scope](#1-purpose-and-scope)
2. [Executive Summary](#2-executive-summary)
3. [Assessment Method](#3-assessment-method)
4. [Repository Overview](#4-repository-overview)
5. [Current Architecture](#5-current-architecture)
6. [Dependency and Event Flows](#6-dependency-and-event-flows)
7. [Code Organization](#7-code-organization)
8. [Data Models](#8-data-models)
9. [Runtime Architecture](#9-runtime-architecture)
10. [Graphical User Interface](#10-graphical-user-interface)
11. [Dashboard](#11-dashboard)
12. [Digital and Analog Simulation](#12-digital-and-analog-simulation)
13. [Trends](#13-trends)
14. [Alarms](#14-alarms)
15. [Feedbacks](#15-feedbacks)
16. [Tag Manager](#16-tag-manager)
17. [PLC Drivers and Protocol Integration](#17-plc-drivers-and-protocol-integration)
18. [Address Parsing and Validation](#18-address-parsing-and-validation)
19. [Persistence and Compatibility](#19-persistence-and-compatibility)
20. [CSV Import and Export](#20-csv-import-and-export)
21. [Settings and User Preferences](#21-settings-and-user-preferences)
22. [Logging and Error Handling](#22-logging-and-error-handling)
23. [Performance and Scalability](#23-performance-and-scalability)
24. [Testing and Verification](#24-testing-and-verification)
25. [Build, Packaging, and Release](#25-build-packaging-and-release)
26. [Security Review](#26-security-review)
27. [Extensibility Assessment](#27-extensibility-assessment)
28. [Architectural Principles](#28-architectural-principles)
29. [Technical Debt Register](#29-technical-debt-register)
30. [Recommended Target Architecture](#30-recommended-target-architecture)
31. [Feedback Engine V2 Readiness](#31-feedback-engine-v2-readiness)
32. [Executive Scorecard](#executive-scorecard)
33. [Top 20 Melhorias](#top-20-melhorias)
34. [Top 10 Quick Wins](#top-10-quick-wins)
35. [Roadmap Arquitetural](#roadmap-arquitetural)
36. [Conclusion](#36-conclusion)

---

# 1. Purpose and Scope

This document records a complete technical review of the PLC Universal Simulator. Its purpose is to establish a durable architectural baseline before implementation of Feedback Engine V2 and before broader platform-oriented work such as OPC UA, MQTT, recipes, scenarios, plugins, web access, REST APIs, multi-client operation, and distributed simulation.

The review covers:

- repository and module organization;
- data models and runtime state;
- event, callback, and thread behavior;
- the desktop user interface;
- Dashboard, Digital, Analog, Trends, Alarms, Feedbacks, and Tag Manager;
- Siemens, Schneider, Generic Modbus, Rockwell, Omron, and Internal Simulator drivers;
- address parsing and validation;
- project, CSV, settings, and preference persistence;
- compatibility and migration;
- logging and exception handling;
- performance and scalability;
- tests, build, packaging, and installers;
- security and plugin readiness;
- technical debt and future architecture.

This is an architectural assessment, not an implementation specification. Recommendations are intentionally incremental and preserve the project's established compatibility rules.

## 1.1 Explicit non-goals

The review does not:

- change the `.simproject` format;
- change application behavior;
- change public APIs;
- require an immediate rewrite;
- prescribe removal of compatibility adapters without evidence;
- treat every large module as defective solely because of its size;
- assume that a future web or distributed runtime must replace the desktop application.

## 1.2 Guiding constraints

The recommendations follow the project rules in `docs/IMPLEMENTATION_RULES.md`:

- preserve backward compatibility;
- prefer incremental refactoring;
- avoid performance regressions;
- preserve working public APIs;
- implement and verify one phase at a time;
- keep project compatibility;
- do not change the application version as a side effect of architecture work.

---

# 2. Executive Summary

PLC Universal Simulator is a functional and well-tested desktop engineering application with a stronger core than the size and procedural style of some UI modules initially suggest. It already solves several difficult engineering concerns:

- a common tag model across multiple PLC brands;
- separation of persistent definitions from volatile runtime values;
- offline and online simulation paths;
- driver isolation behind a service boundary;
- transactional project and CSV loading;
- compatibility with legacy projects;
- responsive master-detail interfaces for thousands of tags;
- incremental Dashboard updates;
- controlled Tk callback shutdown;
- Linux and Windows packaging;
- deterministic, Git-ignored build metadata;
- extensive headless regression tests.

The application is best described as a **modular desktop monolith in active architectural consolidation**. It is not yet a platform architecture. The central application object, `PLCSimulator` in `ui/main_window.py`, acts simultaneously as composition root, controller, mutable state container, scheduler, connection coordinator, simulation facade, project lifecycle coordinator, and shutdown manager. Feature modules communicate through this shared object and through direct cross-module calls.

The principal architectural constraint is therefore not weak local code quality. It is the absence of durable boundaries between:

- domain state;
- application orchestration;
- presentation;
- PLC transport;
- persistence;
- event distribution.

This affects future extensibility. Adding another screen is feasible. Adding another protocol is possible but cross-cutting. Adding a headless runtime, plugin SDK, web API, multiple PLC sessions, or distributed simulation would require substantial extraction work.

## 2.1 Overall assessment

**Overall architecture rating: 6.4/10**

**Current risk:** Medium–High

**Maturity:** Functional, tested desktop product evolving toward a platform

**Readiness for Feedback Engine V2:** Partial; suitable foundations exist, but the engine should not be implemented directly inside the current Feedback UI module.

## 2.2 Principal strengths

1. `core/tag_model.py` and `core/tag_runtime.py` provide a clear definition/runtime split.
2. `services/plc_service.py` is a real service boundary, even though it is currently too broad.
3. `ui/project_config.py` stages and validates project data before applying it.
4. Project and settings writes use temporary files, flushing, `fsync`, and atomic replacement.
5. `drivers/siemens_address.py` centralizes Siemens syntax and type-width validation.
6. Siemens polling groups ranges and isolates failed ranges.
7. Dashboard V2 separates pure presentation state into `core/dashboard_model.py`.
8. Dashboard rows are reconciled incrementally instead of rebuilt each cycle.
9. Digital, Analog, and Trends use bounded master-detail designs.
10. Tk `after()` callbacks are centrally tracked and cancelled during shutdown.
11. The connection attempt runs outside the Tk main thread.
12. The test suite covers a broad range of compatibility and regression cases.
13. Build metadata is generated under `core/generated/` and does not dirty Git.

## 2.3 Principal weaknesses

1. `PLCSimulator` is a god object with broad mutable state and approximately 71 methods.
2. `PLCService` combines driver factory, connection lifecycle, polling, parsing, decoding, writes, caching, and diagnostics.
3. A real import cycle exists among six UI modules.
4. No domain event bus or runtime subscription mechanism exists.
5. PLC reads execute on the Tk thread and can freeze the UI when network calls block.
6. Feedbacks and Alarms retain per-item CustomTkinter widget designs.
7. Several features independently poll the same runtime state.
8. Tag names are mutable but serve as the primary identity across caches and features.
9. Driver APIs are informal and inconsistent.
10. Adding a driver or data type requires changes across many modules.
11. Requirements are not pinned and no repository CI workflow is present.
12. Plugin support is a loader skeleton, not an SDK or security boundary.

---

# 3. Assessment Method

The review used read-only repository inspection and static analysis. It included:

- complete file and directory inventory;
- line counts and module-size comparison;
- Python AST analysis of functions, classes, and imports;
- strongly connected component analysis of the internal import graph;
- review of application, core, service, driver, UI, script, test, packaging, and documentation files;
- review of tracked legacy project examples;
- examination of callbacks, timers, threads, queues, exception handlers, logging, and persistence paths;
- review of existing test organization and recent verified test results;
- review of documented performance measurements.

No build, installer, application startup, or mutating project command is required to interpret this review.

## 3.1 Important interpretation notes

- Module size is treated as a signal, not proof of poor quality.
- Compatibility code is not classified as dead merely because it appears legacy.
- UI code is assessed with the constraints of Tk/CustomTkinter in mind.
- Industrial protocols such as S7 and Modbus have inherent security limitations; those are distinguished from application defects.
- Existing benchmark documents are treated as evidence for current performance, not as guarantees for future workloads.

---

# 4. Repository Overview

## 4.1 Directory structure

```text
plc-universal-simulator/
├── core/          Core data and pure presentation models
├── drivers/       PLC transport implementations and Siemens parser
├── services/      PLC, settings, logging, storage, and plugin services
├── ui/            Desktop widgets, controllers, callbacks, and persistence UI
├── plugins/       Dormant plugin namespace and documentation
├── scripts/       Build, packaging, benchmark, profiling, and integration tools
├── tests/         Headless regression tests
├── templates/     Bundled CSV templates
├── configs/       Example and legacy configuration files
├── packaging/     Desktop integration files
├── docs/          Architecture, build, UI, performance, and SDS documents
├── assets/        Application icons
├── main.py        Application bootstrap
└── plc-universal-simulator.spec
```

## 4.2 Source distribution by responsibility

| Area | Primary responsibility | Assessment |
|---|---|---|
| `core/` | Models and stable identity | Small and generally cohesive |
| `drivers/` | Protocol transports | Clear locally, inconsistent globally |
| `services/` | Application infrastructure | Useful boundary; `PLCService` oversized |
| `ui/` | Presentation and much application logic | Main concentration of coupling |
| `tests/` | Headless regression coverage | Broad and valuable |
| `scripts/` | Operational tooling | Useful but environment-oriented |
| `docs/` | Architecture and feature documentation | Good depth, some drift |

## 4.3 Largest source modules

| Module | Approximate lines | Architectural observation |
|---|---:|---|
| `ui/tag_manager.py` | 1,951 | Too many unrelated responsibilities |
| `ui/main_window.py` | 1,259 | Central controller and state container |
| `ui/project_config.py` | 990 | Serialization, migration, transaction, and UI restore |
| `services/plc_service.py` | 770 | Multi-protocol orchestration and codecs |
| `ui/analog_tab.py` | 764 | Complex presentation plus simulation integration |
| `ui/dashboard_tab.py` | 750 | Large but partially supported by a pure core model |
| `ui/header.py` | 514 | Connection UI for all brands |
| `ui/digital_tab.py` | 502 | Master-detail UI and runtime behavior |
| `ui/analog_profiles.py` | 452 | Simulation state and scheduler |
| `ui/trend_tab.py` | 431 | UI, sampling, storage, and rendering |

---

# 5. Current Architecture

## 5.1 High-level model

```text
                         Project / CSV files
                                  │
                                  ▼
                         TagDefinition list
                                  │
               ┌──────────────────┼──────────────────┐
               │                  │                  │
               ▼                  ▼                  ▼
          UI features        PLCService         Project builder
               │                  │
               │                  ▼
               │          Protocol driver
               │                  │
               └──────────┬───────┘
                          ▼
                  RuntimeTagCache
```

The architecture has three effective layers:

1. **Core and infrastructure:** models, runtime cache, settings, drivers.
2. **Application controller:** primarily `PLCSimulator` and `PLCService`.
3. **Presentation/features:** function-oriented modules under `ui/`.

The boundaries are useful but porous. UI modules frequently import other UI modules, and persistence directly manipulates widgets.

## 5.2 Application composition

`main.py` configures logging and creates `PLCSimulator` from `ui/main_window.py`.

`PLCSimulator` creates:

- `RuntimeTagCache`;
- `PLCService`;
- `AnalogSimulationManager`;
- Tk root and tabs;
- connection state and settings;
- lazy feature tabs;
- callback tracking;
- shared mutable dictionaries and lists.

This makes `PLCSimulator` the de facto service locator. Feature modules receive the whole application rather than narrow dependencies.

## 5.3 Layer-boundary assessment

| Boundary | Current quality | Main issue |
|---|---|---|
| UI → PLC | Good | Routed through `PLCService` |
| UI → Runtime | Direct | Every feature knows the cache |
| UI → UI | Weak | Direct imports and calls |
| Persistence → Domain | Partial | Strong staging but widget-aware application |
| Driver → Service | Informal | No common contract |
| Core → UI | Good | Core does not import Tk |
| Settings → Dashboard | Acceptable | Settings imports pure Dashboard model |

---

# 6. Dependency and Event Flows

## 6.1 Import graph

The core and driver packages are largely acyclic. The principal cycle is:

```text
ui.dashboard_tab
    ↕
ui.digital_tab
    ↕
ui.project_config
    ↕
ui.analog_tab
    ↕
ui.tag_manager
    ↕
ui.alarm_tab
```

Local imports inside functions defer some edges until runtime, preventing immediate import failure but not removing architectural coupling.

### Problem: UI import cycle

- **Description:** Six feature modules depend directly or indirectly on each other.
- **Impact:** Import order is fragile; private helpers become public in practice; isolated testing and extraction become harder.
- **Priority:** P0 / High.
- **Recommendation:** Move cross-feature coordination into application-layer commands/events and make UI modules depend only on narrow controllers or view models.

## 6.2 Event flow

There is no formal domain event system. Runtime changes propagate through:

- explicit function calls;
- feature-specific `after()` timers;
- shared mutable state;
- dirty-tab flags;
- Tk widget events;
- one connection-result queue.

Typical runtime flow:

```text
Tk timer (500 ms)
    │
    ▼
PLCSimulator.start_cyclic_read()
    │
    ├── PLCService.read(tags)
    ├── update Digital/Analog rows
    ├── update Feedback values
    └── update Dashboard
```

Independent timers also update Feedbacks, Dashboard, Alarms, Trends, PID, and Analog simulation.

### Problem: no event-distribution layer

- **Description:** Features poll shared state or call each other directly rather than subscribing to typed changes.
- **Impact:** Duplicate work, hidden dependencies, difficult ordering, no backpressure, and poor readiness for headless or distributed runtimes.
- **Priority:** P0 / High.
- **Recommendation:** Introduce an in-process typed event dispatcher and batched `RuntimeChangeSet` publication. Keep delivery on the Tk thread for presentation subscribers.

## 6.3 State ownership

State is commonly attached dynamically to `app`, for example:

```text
app.tags
app.alarms
app.trend_data
app.feedback_rows
app._dashboard_row_ids
app._analog_profile_cache
app._simulated_values
app._plc_values
```

### Problem: implicit application-state contract

- **Description:** Feature modules create and consume attributes without a declared schema or owner.
- **Impact:** Runtime-only errors, weak type checking, difficult fixtures, and accidental cross-feature mutation.
- **Priority:** P0 / High.
- **Recommendation:** Introduce explicit state objects per feature and pass narrow service/controller dependencies. Preserve compatibility attributes temporarily through adapters.

---

# 7. Code Organization

## 7.1 Cohesive modules

The following modules have clear and limited responsibilities:

- `core/tag_model.py`
- `core/tag_runtime.py`
- `core/connection_state.py`
- `core/dashboard_model.py`
- `core/application_identity.py`
- `drivers/siemens_address.py`
- `services/storage_paths.py`
- `services/settings_service.py`
- `services/logger_service.py`

They provide good examples for future extraction: small public surface, no Tk dependencies, and logic that can be tested directly.

## 7.2 Modules requiring division

### `ui/tag_manager.py`

Responsibilities include:

- widget construction;
- tag CRUD;
- table rendering;
- search;
- name normalization;
- brand compatibility;
- address validation;
- address suggestion;
- universal CSV parsing;
- TIA CSV parsing;
- Schneider CSV parsing;
- CSV export;
- template resolution/export;
- import transaction and rollback.

**Recommendation:** Extract `TagRepository`, `TagValidationService`, `AddressService`, `CSVImportService`, `CSVExportService`, and vendor import adapters.

### `ui/project_config.py`

Responsibilities include dialogs, paths, JSON parsing, schema validation, migration, serialization, project transactions, rollback, widget restoration, alarm rebuilding, trend restoration, PID restoration, and title updates.

**Recommendation:** Create a pure `ProjectStore`, versioned migration pipeline, and feature-specific project contributors.

### `services/plc_service.py`

Responsibilities include driver loading, factory selection, connection, disconnect, read/write routing, address parsing, range planning, decoding, cache updates, diagnostics, and error normalization.

**Recommendation:** Split registry/session/polling/adapter/diagnostics concerns.

### `ui/main_window.py`

Responsibilities include composition, Tk root, tab lifecycle, shared state, PLC connection thread, runtime updates, simulation facade, settings, recent projects, shutdown, logging diagnostics, and error dialogs.

**Recommendation:** Retain it as composition root but delegate behavior to application controllers.

## 7.3 Large functions

Functions over approximately 100 lines include:

- `create_tag_manager_tab()` in `ui/tag_manager.py`;
- `build_project_data()` in `ui/project_config.py`;
- `on_close()` in `ui/main_window.py`;
- `create_dashboard_tab()` in `ui/dashboard_tab.py`;
- `create_trend_tab()` in `ui/trend_tab.py`;
- `apply_imported_tags()` in `ui/tag_manager.py`;
- `read_tags_csv()` in `ui/tag_manager.py`;
- `_apply_project_data()` and `_stage_project_data()` in `ui/project_config.py`.

Large UI constructors are partly unavoidable, but transaction and model functions should be smaller and composable.

## 7.4 Legacy and compatibility code

Known compatibility surfaces include:

- `Tag = TagDefinition`;
- legacy project schema migration;
- legacy settings paths;
- legacy project locations under `configs/`;
- `trend_tag_vars` compatibility state;
- Digital/Analog row helpers used by existing tests;
- alternate old widget restoration paths.

These should be catalogued as compatibility contracts. They should not be removed based only on apparent non-use.

---

# 8. Data Models

## 8.1 TagDefinition

`core/tag_model.py` defines:

```python
@dataclass
class TagDefinition:
    name: str
    data_type: str
    direction: str
    address: str
    enabled_sim: bool = False
    enabled_trend: bool = False
    enabled_alarm: bool = False
    enabled_dashboard: bool = False
    comment: str = ""
```

### Strengths

- Simple and serializable.
- Independent of UI and driver libraries.
- Backward-compatible `Tag` alias.
- Feature flags are explicit.
- Comments are normalized safely.

### Problem: mutable name as identity

- **Description:** Tag name is used as the key in runtime, Trends, alarms, selected rows, simulations, settings, and lookups.
- **Impact:** Renaming can lose associations or require fragile coordinated migration. It is unsuitable for distributed or multi-client synchronization.
- **Priority:** P1 / High.
- **Recommendation:** Add an immutable persistent `tag_id` in a backward-compatible schema migration. Continue exposing `name` as the engineering symbol.

### Problem: string-based type and direction

- **Description:** Data types and directions are repeated as string literals across modules.
- **Impact:** Typographical errors and cross-cutting changes when adding types.
- **Priority:** P1 / Medium–High.
- **Recommendation:** Introduce string-compatible enums and a type capability registry without changing serialized values.

### Problem: limited future metadata

- **Description:** The model lacks units, scaling, engineering range, deadband, access mode, quality policy, vendor metadata, arrays, and structures.
- **Impact:** OPC UA, MQTT, recipes, and advanced visualization will require extensions.
- **Priority:** P2 / Medium.
- **Recommendation:** Add optional metadata objects through versioned schemas rather than adding many unrelated top-level fields.

## 8.2 RuntimeTagCache

`core/tag_runtime.py` stores value, validity, update time, and source.

### Strengths

- Persistent definition state is separated from volatile runtime state.
- Snapshot and restore support rollback.
- Definition signatures prevent preservation across incompatible changes.
- Source-based invalidation supports disconnect semantics.

### Problem: no subscriptions or change sets

- **Description:** Consumers must poll or be manually refreshed.
- **Impact:** Repeated full scans and direct UI calls.
- **Priority:** P0 / High.
- **Recommendation:** Add batch update APIs returning immutable change sets. Publish them through an event dispatcher.

### Problem: not thread-safe

- **Description:** The cache has no synchronization or snapshot isolation.
- **Impact:** Moving PLC polling to a worker could introduce races.
- **Priority:** P0 prerequisite for threaded polling.
- **Recommendation:** Keep mutations in one runtime worker and publish immutable snapshots/change sets, or protect batch swaps with a lock.

### Problem: wall-clock timestamp only

- **Description:** `time.time()` is used without a monotonic sequence.
- **Impact:** Clock adjustments can reorder events.
- **Priority:** P2 / Medium.
- **Recommendation:** Store both UTC wall time and monotonic sequence/timestamp.

## 8.3 Feature data models

Dashboard preferences have a proper pure model in `core/dashboard_model.py`. Alarm, Feedback, Trend, PID, and simulation state are less formal and often represented by dictionaries or parallel attributes.

The Dashboard model should be treated as a successful extraction pattern.

---

# 9. Runtime Architecture

## 9.1 Tk main loop

Tk owns the presentation thread. `PLCSimulator.schedule_job()` wraps `after()`, tracks pending jobs, prevents scheduling during shutdown, and suppresses destruction-related `TclError` appropriately.

This is a significant strength and should remain the only UI callback scheduler.

## 9.2 Connection thread

PLC connection uses:

```text
daemon worker thread
    └── PLCService.connect()
            └── Queue result
                    └── Tk polls every 25 ms
```

This prevents slow connection establishment from freezing the UI.

## 9.3 Cyclic read

`PLCSimulator.start_cyclic_read()` in `ui/main_window.py` calls `PLCService.read()` directly from the Tk callback.

### Critical problem: network I/O on Tk thread

- **Description:** Cyclic PLC reads execute synchronously inside the UI loop.
- **Impact:** Network timeout, driver delay, or large reads can freeze all UI interaction and postpone other timers.
- **Priority:** P0 / Critical.
- **Recommendation:** Introduce a polling worker that owns the driver session. Publish immutable results/change sets to the Tk thread through a bounded queue. Never update widgets from the worker.

## 9.4 Timer inventory

| Feature | Typical interval | Work |
|---|---:|---|
| PLC cyclic read | 500 ms | Network scan and runtime update |
| Feedback scan | 500 ms | Iterate all feedback rows |
| Alarm scan | 500 ms | Evaluate all alarms and update rows |
| Dashboard | 750 ms | Cards, population, rows, details, panels |
| Trends | 1000 ms | Sample, trim, redraw, table update |
| PID | Configurable | Read, calculate, write |
| Analog profiles | Configurable | State transition and write |

### Problem: redundant feature polling

- **Description:** Feedbacks and Dashboard are updated both by their own timers and by PLC read paths.
- **Impact:** Duplicate CPU and widget configuration work; harder update ordering.
- **Priority:** P1 / Medium–High.
- **Recommendation:** Coalesce runtime-driven UI refresh into one frame/update coordinator using change sets and dirty feature flags.

## 9.5 Shutdown

`PLCSimulator.on_close()` is robust but broad. It performs unsaved checks, confirmation, timer cancellation, Trend/PID/profile shutdown, worker joins, disconnect, settings save, Matplotlib cleanup, diagnostics, root destruction, and log flushing.

### Problem: shutdown orchestration is monolithic

- **Description:** Production shutdown and profiling instrumentation coexist in a 143-line method.
- **Impact:** Hard to reason about ordering and extend safely.
- **Priority:** P2 / Medium.
- **Recommendation:** Introduce a `ShutdownCoordinator` with registered idempotent lifecycle participants and bounded phases.

---

# 10. Graphical User Interface

## 10.1 Current style

UI modules primarily expose functions accepting `app`. This avoids a deep widget inheritance hierarchy and makes many functions easy to monkeypatch. However, each module receives far more authority than it needs.

## 10.2 Reuse

Reusable components include:

- `SafeScrollableFrame` in `ui/scrollable_frame.py`;
- table helpers and tooltips in `ui/table_utils.py`;
- pure Dashboard helpers in `core/dashboard_model.py`;
- master-detail patterns in Digital, Analog, and Trends.

The master-detail implementations are similar but not yet consolidated into a shared table controller.

## 10.3 UX consistency

Strengths:

- keyboard navigation in modern tables;
- searchable views;
- explicit status and quality;
- comments and tooltips;
- recent projects;
- empty states;
- persistent Dashboard layouts;
- appropriate default CSV/project directories.

Issues:

- mixed Portuguese and English labels;
- inconsistent error presentation;
- different table implementations across tabs;
- Feedbacks and Alarmes lack modern filtering and selection;
- some operations silently update a status label instead of explaining validation failure;
- `open_project_folder()` is Linux-specific.

### Problem: inconsistent UI architecture

- **Description:** Some tabs use scalable Treeviews; older tabs use per-item CTk widgets.
- **Impact:** Uneven performance, accessibility, sorting, keyboard support, and maintenance.
- **Priority:** P1 / High.
- **Recommendation:** Standardize on a reusable master-detail table pattern with feature-specific columns and editors.

---

# 11. Dashboard

## 11.1 Architecture

Dashboard is split between:

- `core/dashboard_model.py`: column registry, preference validation, filtering, sorting, statistics, auto-fit;
- `ui/dashboard_tab.py`: widgets, bindings, row reconciliation, selected-tag panel, navigation, events, and scheduling.

This is the strongest current example of presentation-state separation.

## 11.2 Performance design

Dashboard:

- maintains stable row IDs;
- removes only rows no longer required;
- inserts only new rows;
- compares row snapshots;
- calls `Treeview.set()` only for changed cells;
- preserves selection;
- avoids rebuilding when columns change;
- bounds auto-fit sampling;
- separates static and dynamic Selected Tag detail signatures.

## 11.3 Problems

### Dashboard orchestration is compressed and broad

- **Description:** `update_dashboard()` updates cards, table, diagnostics, alarm summary, Trend summary, simulation summary, project state, and version text.
- **Impact:** Difficult testing, formatting maintenance, and incremental optimization.
- **Priority:** P2 / Medium.
- **Recommendation:** Split into summary view models and per-panel renderers, each with an immutable signature.

### Full-population work remains periodic

- **Description:** Tag compatibility, filtering, sorting, statistics, and row tuples are recomputed over the population.
- **Impact:** O(n) work continues even when only one runtime value changes.
- **Priority:** P1 for 5,000+ sustained workloads.
- **Recommendation:** Maintain a cached population/index and update affected statistics/rows using runtime change sets.

### Event severity inferred from text

- **Description:** `record_dashboard_event()` derives severity from words such as `error` or `warning`.
- **Impact:** Localization and message wording can alter semantics.
- **Priority:** P2 / Medium.
- **Recommendation:** Require typed severity and event code at call sites; keep text as presentation.

---

# 12. Digital and Analog Simulation

## 12.1 Strengths

- One heavy editor per tab rather than widgets per tag.
- Treeview pagination.
- Bounded insertion and update work.
- Selected-tag preservation.
- Runtime-source comparison.
- Highlighting changed values.
- Canonical analog profile state separated from transient widgets.
- Batch scheduling when widget pools must be expanded for compatibility paths.

## 12.2 Problems

### Repeated master-detail logic

- **Description:** Search, pagination, sorting, selection, headings, and context behavior are implemented separately in Digital, Analog, and Trends.
- **Impact:** Bug fixes and UX improvements must be repeated.
- **Priority:** P2 / Medium.
- **Recommendation:** Extract a generic `PagedTreeController` or composable helpers, not a large inheritance framework.

### Siemens-oriented analog defaults

- **Description:** UI ranges such as `0..27648` are embedded in several paths.
- **Impact:** Generic engineering units and other protocols are constrained.
- **Priority:** P2 / Medium.
- **Recommendation:** Derive ranges from tag metadata/type capabilities while preserving current defaults.

### Parallel state collections

- **Description:** Digital and Analog maintain lists and dictionaries keyed by indexes/names alongside canonical tags.
- **Impact:** Rename, reorder, and refresh operations require coordination.
- **Priority:** P1 / Medium–High.
- **Recommendation:** Use tag IDs and feature state repositories; keep index lists only as transient views.

---

# 13. Trends

## 13.1 Strengths

- Fixed master-detail structure.
- Persistent Matplotlib figure.
- No checkbox or Tk variable per tag.
- Bounded table page.
- Callback cancellation during destruction.
- CSV export to the dedicated CSV directory.

## 13.2 Problems

### Full chart redraw

- **Description:** `redraw_trend()` clears axes and recreates every visible line.
- **Impact:** CPU grows with visible curves and buffer size.
- **Priority:** P1 for advanced Trends/Dashboard V3.
- **Recommendation:** Maintain line artists and update their data incrementally; decouple sampling from rendering.

### Sampling tied to Tk

- **Description:** Trend history is sampled through a Tk `after()` callback.
- **Impact:** UI stalls distort sampling and a headless historian cannot reuse it.
- **Priority:** P1 / High for future runtimes.
- **Recommendation:** Introduce a Trend/History service receiving runtime events or snapshots on an independent clock.

### Configuration semantics incomplete

- **Description:** Editor fields such as `sample_rate_ms` and `history_size` are not fully reflected in the global sampling loop.
- **Impact:** UI promises can diverge from actual behavior.
- **Priority:** P1 / Medium–High.
- **Recommendation:** Define and test exact per-tag sampling and retention semantics.

### Memory growth model

- **Description:** Python lists hold time and value objects per tag.
- **Impact:** Large curve counts and buffers consume substantial memory.
- **Priority:** P2 / Medium.
- **Recommendation:** Use bounded ring buffers or numeric arrays in a historian abstraction.

---

# 14. Alarms

## 14.1 Current behavior

`ui/alarm_tab.py` stores alarm dictionaries and scans them every 500 ms. HIGH/HIGH HIGH use `value > limit`; LOW/LOW LOW use `value < limit`. Alarm activation, return-to-normal, acknowledgement, and Dashboard messages are handled directly in the UI module.

## 14.2 Problems

### Alarm state represented by dictionaries

- **Description:** Configuration and runtime fields share mutable dictionaries.
- **Impact:** Weak validation, no explicit lifecycle, difficult persistence and extension.
- **Priority:** P1 / High.
- **Recommendation:** Create `AlarmDefinition`, `AlarmRuntime`, and a pure state evaluator.

### Quality BAD becomes normal

- **Description:** Missing/invalid runtime values set `active=False`.
- **Impact:** Loss of communication can appear as a normal process condition.
- **Priority:** P0 / High in industrial semantics.
- **Recommendation:** Represent `BAD_QUALITY` or `UNKNOWN` separately. Define policy for retaining the previous alarm state.

### No hysteresis or delay

- **Description:** Limits have immediate transitions without deadband, on-delay, or off-delay.
- **Impact:** Chattering and noisy event histories.
- **Priority:** P1 / High for production use.
- **Recommendation:** Add optional hysteresis and temporal policies in a domain engine.

### Per-alarm widgets

- **Description:** Every alarm creates a row frame and multiple CTk widgets.
- **Impact:** Poor scalability and inconsistent table UX.
- **Priority:** P1 / High.
- **Recommendation:** Use incremental Treeview plus a selected-alarm editor.

---

# 15. Feedbacks

## 15.1 Current behavior

`ui/feedback_tab.py` interprets tags with `direction == "Feedback"` as display rows. It has no domain engine. It recreates all row widgets during refresh and polls the runtime cache every 500 ms.

## 15.2 Current strengths

- Reuses the central tag database.
- Reuses runtime quality/value handling.
- Supports comments.
- Does not access drivers directly.
- Scheduling uses the application callback tracker.

## 15.3 Architectural gap

The current feature is a feedback monitor, not a Feedback Engine. It cannot express:

- command/feedback pairing;
- expected state;
- inversion;
- transition delay;
- timeout;
- mismatch;
- bad-quality policy;
- acknowledgement;
- interlocks;
- state-machine history;
- severity;
- engine events.

### Problem: no Feedback domain model

- **Description:** Feedback is inferred only from tag direction.
- **Impact:** Feedback Engine V2 behavior would otherwise be embedded in widgets and dictionaries.
- **Priority:** P0 / Critical before V2.
- **Recommendation:** Introduce pure `FeedbackDefinition`, `FeedbackRuntime`, and state-transition logic before changing UI.

### Problem: one timer or widget path must not be added per feedback

- **Description:** The existing view already creates widgets per row and scans all rows.
- **Impact:** Thousands of feedbacks would be slow and memory-heavy.
- **Priority:** P0 / High.
- **Recommendation:** Use one engine evaluation pass over changed dependencies and one master-detail Treeview.

### Problem: limited tests

- **Description:** Feedback-specific automated coverage is minimal compared with other features.
- **Impact:** High regression risk during V2 work.
- **Priority:** P0 / High.
- **Recommendation:** Build a comprehensive engine test matrix before UI integration.

---

# 16. Tag Manager

## 16.1 Role

The Tag Manager is the current source of truth for tag definitions. It provides:

- CRUD;
- table view;
- name validation;
- brand compatibility;
- address validation and suggestion;
- feature flags;
- search;
- CSV workflows;
- templates.

## 16.2 Strengths

- Case-insensitive unique-name validation.
- Brand-aware address handling.
- Support for Siemens extended numeric types.
- Comment preservation and search.
- Transactional imports.
- No partial replacement on invalid CSV.
- Explicit compatible-tag selectors for each feature.

## 16.3 Problems

### Monolithic module

- **Description:** `ui/tag_manager.py` has nearly 2,000 lines and owns UI, domain validation, vendor formats, and transactions.
- **Impact:** High change surface and difficult reuse by REST, plugins, or headless runtime.
- **Priority:** P1 / High.
- **Recommendation:** Extract pure services while retaining existing UI entry points as adapters.

### Repeated linear lookup

- **Description:** Tags are repeatedly searched by name using list scans.
- **Impact:** O(n) operations accumulate across features.
- **Priority:** Quick win / P1.
- **Recommendation:** Introduce a repository with indexes by immutable ID and normalized name.

### Compatibility validation repeatedly reparses addresses

- **Description:** Feature selectors may validate each tag every time they are called.
- **Impact:** Repeated work on Dashboard, Alarm, Feedback, and Trends refreshes.
- **Priority:** P1 / Medium–High.
- **Recommendation:** Cache normalized address/capability results and invalidate them only on structural changes.

---

# 17. PLC Drivers and Protocol Integration

## 17.1 Driver inventory

| Driver | Module | Transport style |
|---|---|---|
| Siemens S7 | `drivers/siemens_s7.py` | Absolute areas and grouped range reads |
| Schneider Modbus | `drivers/schneider_modbus.py` | Coils and holding registers |
| Generic Modbus TCP | `drivers/modbus_tcp.py` | Thin Schneider transport reuse |
| Rockwell EtherNet/IP | `drivers/rockwell_enip.py` | Symbolic batch tags |
| Omron FINS | `drivers/omron_fins.py` | CIO/DM typed operations |
| Internal Simulator | `drivers/internal_simulator.py` | In-process typed memory |

## 17.2 Driver abstraction

There is no formal common interface. Driver methods differ by protocol. `PLCService` understands each concrete surface and contains brand-specific branches.

### Problem: no driver contract

- **Description:** Drivers do not implement a common `Protocol`, capability model, or adapter interface.
- **Impact:** Adding drivers requires modifications throughout the application and prevents plugin-based drivers.
- **Priority:** P0/P1 / High.
- **Recommendation:** Define a small session interface plus capability-specific operations. Avoid forcing protocols into one oversized interface.

Suggested conceptual contracts:

```python
class DriverSession(Protocol):
    def connect(self, settings: ConnectionSettings) -> None: ...
    def disconnect(self) -> None: ...
    def is_connected(self) -> bool: ...

class TagReader(Protocol):
    def read(self, requests: Sequence[ReadRequest]) -> ReadBatchResult: ...

class TagWriter(Protocol):
    def write(self, request: WriteRequest) -> WriteResult: ...
```

Protocol adapters can translate generic requests into optimized ranges or symbolic batches.

## 17.3 PLCService

`services/plc_service.py` performs useful isolation but violates Single Responsibility and Open/Closed principles.

Recommended split:

```text
DriverRegistry
PLCSession
PollingEngine
ReadPlanner/ProtocolAdapter
RuntimeUpdater
DiagnosticsCollector
```

## 17.4 Siemens

Strengths:

- dedicated parser;
- DB/M/I/Q support;
- German input/output normalization;
- type-width validation;
- read-only Input protection;
- compact read ranges;
- range failure isolation.

Risks:

- decoding remains inside `PLCService`;
- no explicit cancellation/timeout abstraction;
- typed transport errors are not propagated;
- optimized DB constraints are documentation-only.

## 17.5 Schneider and Generic Modbus

Strengths:

- block read limits;
- signed INT handling;
- REAL register handling;
- compatibility with alternate pymodbus device keyword names.

Risks:

- fixed endian/word order;
- signature introspection per request;
- address origin semantics not modeled;
- parsing split across service and UI.

## 17.6 Internal Simulator

The simulator is valuable because it follows the same service path as physical PLCs.

Future improvements may include:

- memory keyed by canonical address and type;
- controllable latency;
- injected read/write errors;
- quality simulation;
- deterministic virtual clock;
- snapshots;
- multi-session isolation.

---

# 18. Address Parsing and Validation

## 18.1 Siemens parser

`drivers/siemens_address.py` is cohesive and testable. It returns a structured immutable `SiemensAddress` with normalized address, area, DB, unit, offsets, and width.

This is the preferred architectural model for all protocols.

## 18.2 Other protocols

Schneider, Generic Modbus, Rockwell, and Omron parsing is less centralized and is partly embedded in `PLCService` and `ui/tag_manager.py`.

### Problem: inconsistent address architecture

- **Description:** Siemens has a structured address model; other protocols mostly return primitive strings/integers.
- **Impact:** Validation, suggestions, reads, writes, and future plugins duplicate protocol knowledge.
- **Priority:** P1 / High.
- **Recommendation:** Define protocol-specific immutable address objects and `AddressCodec` interfaces.

### Problem: type capability rules are scattered

- **Description:** Supported data types are repeated in project staging, Tag Manager, service routing, and drivers.
- **Impact:** Adding a type requires broad coordinated changes.
- **Priority:** P1 / High.
- **Recommendation:** Introduce a protocol/type capability registry used by validation, UI, import, and runtime.

---

# 19. Persistence and Compatibility

## 19.1 Project files

`ui/project_config.py` uses JSON with `.simproject` extension and fields including:

```text
format
version
schema_version
plc
tags
runtime_settings
alarms
pid
trends
dashboard
analog_profiles
```

Tracked legacy examples under `configs/` have project `version=1` and may omit `schema_version`, confirming that migration behavior remains operationally important.

## 19.2 Transactional loading

The current sequence is sound:

1. Parse JSON.
2. Migrate in memory.
3. Validate structure.
4. Normalize tags and sections.
5. Stage a deep copy.
6. Apply to UI/runtime.
7. Roll back on failure.

## 19.3 Atomic saving

Project and settings writes use temporary files, flush, `fsync`, and `os.replace`. This is a strong reliability characteristic.

## 19.4 Problems

### Persistence is UI-aware

- **Description:** Applying or building projects reads and writes many widgets directly.
- **Impact:** Headless runtime, REST API, and isolated migration tests are difficult.
- **Priority:** P1 / High.
- **Recommendation:** Introduce a pure project aggregate and feature contributors. UI observes the applied aggregate.

### Central project builder grows with every feature

- **Description:** `build_project_data()` must know all feature state.
- **Impact:** Feedback Engine V2 and future features increase coupling.
- **Priority:** P1 / High.
- **Recommendation:** Define `ProjectContributor` adapters with `serialize`, `stage`, `apply`, and `rollback` responsibilities.

### No formal schema document

- **Description:** Validation exists only in Python code.
- **Impact:** External tooling and migration reasoning are harder.
- **Priority:** P2 / Medium.
- **Recommendation:** Publish JSON Schema as documentation and test it against legacy fixtures; keep Python validation authoritative during migration.

---

# 20. CSV Import and Export

## 20.1 Strengths

- UTF-8 BOM, UTF-8, CP1252, and Latin-1 support.
- Universal field aliases.
- Optional comments with localized aliases.
- Vendor importers for Siemens and Schneider.
- Whole-file validation before replacement.
- Runtime/UI rollback on failed application.
- Dedicated CSV directory.
- Bundled templates.

## 20.2 Problems

### Whole-file memory loading

- **Description:** `_open_csv_text()` reads the complete file as bytes.
- **Impact:** Large or malicious local files can consume excessive memory and freeze the UI.
- **Priority:** P2 / Medium.
- **Recommendation:** Enforce configurable byte/row/cell limits and move parsing off the UI thread for large imports.

### CSV logic resides in UI module

- **Description:** Parsing and writing are implemented in `ui/tag_manager.py`.
- **Impact:** REST, plugins, tests, and batch conversion cannot depend on a clean service boundary.
- **Priority:** P1 / High.
- **Recommendation:** Extract pure import/export adapters under infrastructure/services.

### Duplicate templates

- **Description:** Siemens template copies exist at multiple paths.
- **Impact:** Content can drift.
- **Priority:** P3 / Low.
- **Recommendation:** Establish `templates/` as the only canonical source and retain compatibility copies only if required and tested.

---

# 21. Settings and User Preferences

## 21.1 Current design

`services/settings_service.py` stores:

- PLC brand;
- IP address;
- last/recent projects;
- window size;
- last project folder;
- UI preferences;
- versioned Dashboard preferences.

Frozen builds use platform-appropriate configuration roots. Source mode uses `config/settings.json` inside the repository.

## 21.2 Strengths

- Settings are separate from projects.
- Invalid fields recover independently.
- Dashboard preferences have versioning and migration.
- Writes are atomic.
- Legacy frozen settings can be migrated.

## 21.3 Problems

### General settings have no schema version

- **Description:** Only the Dashboard subsection has an explicit version.
- **Impact:** Future migration logic will become implicit.
- **Priority:** P2 / Medium.
- **Recommendation:** Add a top-level settings schema version with partial-field recovery.

### Source settings depend on repository location

- **Description:** Source execution writes under the checkout.
- **Impact:** Multiple checkouts have different settings; read-only source trees fail; settings may be accidentally inspected as project data.
- **Priority:** P2 / Medium.
- **Recommendation:** Use the same platform user-config path in source and frozen modes, with an explicit developer override.

### Silent load fallback

- **Description:** Invalid JSON or I/O failure returns defaults without logging.
- **Impact:** Users may perceive preferences as randomly lost.
- **Priority:** P2 / Medium.
- **Recommendation:** Log validation/load failures and optionally retain a `.broken` copy.

---

# 22. Logging and Error Handling

## 22.1 Logging

`services/logger_service.py` configures UTF-8 file logging and a warning-level console handler. It avoids duplicate application handlers.

### Strengths

- Central configuration.
- Context-rich PLC logs.
- Startup and shutdown diagnostics.
- Full traceback capture for unexpected callbacks.
- Flush during shutdown.

### Problem: no log rotation

- **Description:** A single file grows without a configured size or retention limit.
- **Impact:** Long-running deployments can consume disk space.
- **Priority:** Quick win / P1.
- **Recommendation:** Use `RotatingFileHandler` or timed rotation with conservative retention.

### Problem: frozen log location may be unwritable

- **Description:** Frozen builds default beside the executable.
- **Impact:** System-wide or read-only installation locations can prevent startup logging.
- **Priority:** P1 / Medium–High.
- **Recommendation:** Store logs under a per-user state/log directory.

## 22.2 Error taxonomy

Many driver/service errors are caught as `Exception` and converted to `None` or `False`.

### Problem: loss of error semantics

- **Description:** Timeout, validation, permission, protocol, connection, and decoding failures often converge into the same result.
- **Impact:** UI messages, retries, metrics, and alarms cannot make informed decisions.
- **Priority:** P1 / High.
- **Recommendation:** Introduce typed results/errors such as `ConnectionError`, `TimeoutError`, `AddressError`, `PermissionError`, `ProtocolError`, and `BadQuality` while preserving current public return adapters.

## 22.3 Unexpected error dialog

`PLCSimulator._report_callback_exception()` logs and shows a generic modal. This is appropriate as a final safety net but should not substitute for domain error handling. Repeated exceptions could produce repeated modal dialogs.

---

# 23. Performance and Scalability

## 23.1 Existing evidence

`docs/UI_PERFORMANCE.md`, `docs/DASHBOARD.md`, and `docs/TRENDS.md` document successful optimization for 100, 1,000, and 5,000-tag scenarios.

Digital and Analog replaced per-tag control sets with bounded Treeviews and one reusable editor. Trends removed per-tag Tk variables/widgets. Dashboard performs incremental cell updates.

## 23.2 Complexity by feature

| Operation | Approximate behavior |
|---|---|
| Runtime cache sync | O(number of tags) |
| PLC scan planning | O(number of tags) plus grouping |
| Dashboard filter/statistics | O(number of dashboard tags) |
| Dashboard sort | O(n log n) when recomputed |
| Digital/Analog visible update | O(page size) |
| Alarm scan | O(number of alarms) |
| Feedback update | O(number of feedback rows) |
| Trend sample | O(enabled trend tags) |
| Trend redraw | O(visible curves × points) |

## 23.3 Aggregate workload

At 5,000 tags, overall cost is not just a single table refresh:

```text
runtime sync
+ protocol parsing/planning
+ PLC reads/decoding
+ Digital page refresh
+ Analog page refresh
+ Feedback scan
+ Alarm evaluation
+ Dashboard filtering/statistics/reconciliation
+ Trend sampling/rendering
```

Independent timers may perform overlapping work even when runtime values did not change.

## 23.4 Key performance problems

### Runtime definitions synchronized every scan

- **Description:** `RuntimeTagCache.sync()` rebuilds definition/value dictionaries during every `PLCService.read()`.
- **Impact:** O(n) allocation at every polling interval.
- **Priority:** P1 / Medium–High.
- **Recommendation:** Synchronize only when the tag-definition generation changes.

### Repeated compatibility parsing

- **Description:** Feature selectors may revalidate the same addresses.
- **Impact:** Avoidable CPU at 5,000 tags.
- **Priority:** P1 / Medium.
- **Recommendation:** Cache normalized capabilities per tag-definition generation.

### Legacy Feedback and Alarm UI

- **Description:** Widgets scale with item count.
- **Impact:** Memory, construction time, shutdown cost, and layout latency grow linearly with high constants.
- **Priority:** P1 / High.
- **Recommendation:** Convert both to bounded Treeview/master-detail implementations.

## 23.5 Scale readiness

| Workload | Assessment |
|---|---|
| 100 tags | Strong |
| 1,000 tags | Strong in modern tabs |
| 5,000 tags | Acceptable with feature-specific risks |
| 10,000+ tags | Not demonstrated |
| Thousands of Feedback rows | Not ready |
| Thousands of Alarm rows | Not ready |
| Thousands of visible Trend curves | Not ready |
| Multiple PLC sessions | Not supported |
| Multiple clients | Not supported |

---

# 24. Testing and Verification

## 24.1 Current test portfolio

The repository contains broad tests covering:

- tag model and runtime cache;
- address validation;
- Siemens multi-area behavior;
- Schneider/Modbus routing;
- Omron and Rockwell drivers;
- Internal Simulator;
- PLC service;
- project files and migration;
- CSV import, templates, and comments;
- Digital and Analog refresh/simulation;
- Dashboard and Dashboard V2;
- Trends;
- settings and storage paths;
- connection lifecycle and shutdown;
- logging, About, version generation, and packaging;
- plugin loader skeleton.

The complete suite contained approximately 460 passing tests at the reviewed baseline.

## 24.2 Strengths

- Headless by default.
- Protocol libraries are mockable.
- Regression tests preserve legacy behavior.
- Transaction failure paths are tested.
- Shutdown has unusually thorough coverage.
- Performance harnesses are included.
- Dashboard pure logic is directly testable.

## 24.3 Gaps

| Gap | Impact | Priority | Recommendation |
|---|---|---:|---|
| Minimal Feedback tests | V2 regression risk | P0 | Build engine matrix first |
| No dedicated Alarm suite | Weak alarm semantics coverage | P1 | Test quality, ACK, transitions, persistence |
| No driver contract tests | New drivers vary silently | P1 | Shared adapter test suite |
| No coverage reporting | Unknown unexecuted branches | P2 | Add coverage threshold/report |
| No fuzz/property tests | Parsers may miss edge cases | P2 | Fuzz JSON/CSV/address parsers |
| No concurrency tests | Polling-worker refactor risk | P1 | Test queue, cancellation, races |
| No hardware-in-loop suite | Mock/real divergence | P2 | Optional gated integration tests |
| No CI workflow | Platform regressions | P1 | Linux and Windows CI |
| Limited packaged E2E | Frozen-only failures | P1 | Smoke executable in virtual display/Windows runner |
| No hostile-size tests | Memory/UI DoS risk | P2 | Enforce and test limits |

## 24.4 Test architecture recommendation

Future tests should increasingly target:

- pure domain state machines;
- command handlers;
- immutable runtime change sets;
- driver contracts;
- project contributors;
- adapters at UI boundaries.

Widget-detail assertions should remain only where presentation behavior itself is the requirement.

---

# 25. Build, Packaging, and Release

## 25.1 Version architecture

The current version architecture is:

```text
Git state
    └── scripts/generate_version.py
            └── core/generated/build_metadata.py  [Git ignored]
                    └── core/version.py adapter
                            └── source or PyInstaller runtime
```

`core/version.py` preserves the public constants and fallback. Builds do not modify tracked source files.

## 25.2 Linux

`scripts/build_linux.sh` generates metadata and runs the shared PyInstaller spec. `scripts/install_linux.sh` installs a one-folder application under the user's local share directory, creates a launcher symlink, and installs desktop/icon metadata.

Strengths:

- no root requirement;
- canonical application identity;
- one-folder startup performance;
- isolated user installation;
- uninstall helper.

Limitations:

- no DEB/RPM/Flatpak/AppImage;
- no signing or release manifest;
- no automatic update;
- environment dependencies are not locked.

## 25.3 Windows

The same spec creates `PLC Universal Simulator.exe`. Batch scripts build, install to `%LOCALAPPDATA%`, create a shortcut, and preserve user data during uninstall.

Limitations:

- no MSI/MSIX;
- no code signing;
- no native Windows version resource;
- PowerShell installation logic is embedded in a batch file;
- no automated Windows build workflow is present.

## 25.4 Reproducibility

Build metadata uses `SOURCE_DATE_EPOCH`, then commit timestamp, then wall time. This improves deterministic metadata.

Full reproducibility is not guaranteed because `requirements.txt` contains unpinned dependency names.

### Problem: unpinned dependencies

- **Description:** Runtime, driver, test, and packaging dependencies have no versions or hashes.
- **Impact:** Builds from the same commit may use incompatible or different packages.
- **Priority:** P1 / High.
- **Recommendation:** Maintain tested lock/constraint files per supported Python/platform combination and update them deliberately.

### Problem: no CI/release automation

- **Description:** No repository workflow validates Linux and Windows builds on each relevant change.
- **Impact:** Packaging failures are discovered manually.
- **Priority:** P1 / High.
- **Recommendation:** Add test, compile, packaging smoke, artifact manifest, and clean-worktree checks in CI.

---

# 26. Security Review

## 26.1 Trust model

The current application is a local desktop engineering tool. It assumes that the operator can:

- open project and CSV files;
- configure PLC endpoints;
- perform PLC writes;
- explicitly load Python modules through the dormant plugin service if invoked programmatically.

This is acceptable for the current local model but insufficient for web, REST, multi-user, or plugin marketplace scenarios.

## 26.2 Input validation

Strong areas:

- Siemens address validation;
- project format/version checks;
- tag name/type/direction validation;
- CSV header and boolean parsing;
- Omron port/node ranges;
- atomic application of imported data.

## 26.3 Problems

### Unbounded project and CSV files

- **Description:** JSON and CSV inputs have no explicit byte, row, nesting, or cell-length limits.
- **Impact:** Local denial of service through memory or CPU exhaustion.
- **Priority:** P2 / Medium.
- **Recommendation:** Define limits, validate before full application, and report them clearly.

### PLC writes lack authorization policy

- **Description:** Write permission is based mainly on address/type and Siemens Input protection.
- **Impact:** Future multi-user/API use could permit unsafe writes.
- **Priority:** P1 before network APIs.
- **Recommendation:** Add command authorization, allowlists, audit records, and optional confirmation/interlock policies.

### Plugin loader executes arbitrary code

- **Description:** `services/plugin_service.py` imports supplied Python modules.
- **Impact:** A plugin has full process/user privileges.
- **Priority:** P1 before enabling plugins.
- **Recommendation:** Treat plugins as trusted code initially, require manifests/signatures/compatibility declarations, and consider process isolation for untrusted extensions.

### Logs may contain sensitive operational data

- **Description:** IPs, paths, tag names, addresses, and tracebacks may be logged.
- **Impact:** Operational information exposure.
- **Priority:** P2 / Medium.
- **Recommendation:** Document log contents, rotate securely, and redact future credentials/tokens.

## 26.4 Protocol security

S7, Modbus TCP, EtherNet/IP, and FINS commonly operate without application-level TLS or authentication. Future remote or distributed deployment should place protocol communications behind network segmentation, secure gateways, VPNs, or protocol-specific secure modes where available.

---

# 27. Extensibility Assessment

## 27.1 Adding a PLC driver

Current effort is high. Likely changes include:

- `services/plc_service.py` driver imports, connection, reads, and writes;
- `core/connection_state.py`;
- `ui/header.py`;
- `ui/tag_manager.py` validation/suggestion/template mapping;
- `ui/project_config.py` supported brands/settings;
- templates;
- PyInstaller hidden imports;
- tests and documentation.

**Assessment:** 4/10.

## 27.2 Adding a Dashboard

A new fixed desktop dashboard can reuse tags/runtime, but there is no dashboard plugin/view registration interface.

**Assessment:** 6/10 for built-in code, 3/10 for extensions.

## 27.3 Adding widgets

Adding widgets inside existing tabs is straightforward. Reusable independent widgets are harder because state is obtained from `app` rather than injected interfaces.

**Assessment:** 6/10 built-in, 4/10 reusable.

## 27.4 Adding data types

Data types are checked in Tag Manager, project staging, drivers, `PLCService`, simulation, CSV, tables, and PID/Alarm selectors.

**Assessment:** 3/10.

## 27.5 Adding protocols

Possible but cross-cutting. A protocol adapter/capability registry is needed.

**Assessment:** 4/10.

## 27.6 Creating plugins

`PluginService` only imports named modules. There is no:

- discovery;
- manifest;
- lifecycle;
- registration API;
- capability API;
- UI extension point;
- settings namespace;
- project-data namespace;
- compatibility contract;
- permission model;
- isolation.

**Assessment:** 2/10.

## 27.7 Future-feature readiness

| Feature | Readiness | Required foundation |
|---|---|---|
| Feedback Engine V2 | Partial | Domain model, events, scalable view |
| Dashboard V3 | Good–Partial | View models, cached runtime indexes |
| Recipes | Partial | Tag IDs, command service, project contributor |
| Scenario Engine | Low–Partial | Clock, command/event model, deterministic runtime |
| OPC UA | Partial | Driver registry, richer types, subscriptions |
| MQTT | Low | Pub/sub model, topic mapping, security |
| Plugin SDK | Low | Stable ports, lifecycle, manifest, isolation |
| Web Runtime | Low | Headless application layer |
| REST API | Low | Commands/queries, auth, headless runtime |
| Multi-client | Very low | Concurrent state, auth, conflict strategy |
| Distributed simulation | Very low | Stable IDs, event transport, clocks, consistency |

---

# 28. Architectural Principles

## 28.1 SOLID

### Single Responsibility

Strong in core models and parser modules. Weak in `PLCSimulator`, `PLCService`, Tag Manager, and project configuration.

### Open/Closed

Weak for drivers, protocols, brands, and data types because central conditionals require modification.

### Liskov Substitution

No common driver abstraction exists, so substitution is informal and enforced by service branches.

### Interface Segregation

UI modules receive the entire application object rather than narrow interfaces.

### Dependency Inversion

Core is independent, but application/UI code depends on concrete modules and shared state.

## 28.2 DRY

Moderate. Important parsing and persistence paths are centralized, but table behavior, tag lookups, compatibility checks, and callback patterns are repeated.

## 28.3 KISS

Core models and individual drivers are simple. The procedural UI style began simple but accumulated implicit state and cross-calls.

## 28.4 Separation of Concerns

The definition/runtime split is good. UI/application/persistence separation remains incomplete.

## 28.5 Composition over Inheritance

The project generally favors composition. This is positive. The main issue is composition through a global application object rather than explicit components.

## 28.6 Encapsulation

Weak at the application level because feature state is publicly mutable on `app`.

## 28.7 Testability

Good in practice due to headless fakes and pure helper extraction. It can improve significantly with domain/application layers.

---

# 29. Technical Debt Register

| ID | Location | Problem | Impact | Priority | Recommendation |
|---|---|---|---|---:|---|
| TD-001 | `ui/main_window.py` | God object | High coupling and growth | P0 | Extract controllers/state |
| TD-002 | `ui/main_window.py` | PLC read on Tk thread | UI freezes on slow I/O | P0 | Polling worker + queue |
| TD-003 | UI import graph | Six-module cycle | Fragile imports and APIs | P0 | Application event/command layer |
| TD-004 | `ui/feedback_tab.py` | No Feedback domain | V2 cannot scale cleanly | P0 | Pure Feedback Engine |
| TD-005 | Runtime | No subscriptions/change sets | Repeated scans | P0 | Event dispatcher |
| TD-006 | `services/plc_service.py` | Broad service | Hard driver extension | P1 | Registry/session/adapters |
| TD-007 | Drivers | No formal contract | Inconsistent implementations | P1 | Protocol/capability interfaces |
| TD-008 | `core/tag_model.py` | Mutable name identity | Rename/distribution fragility | P1 | Persistent `tag_id` |
| TD-009 | `ui/alarm_tab.py` | Dict model and BAD→normal | Incorrect industrial semantics | P0/P1 | Alarm domain states |
| TD-010 | Feedback/Alarm UI | Widgets per item | Poor large-scale behavior | P1 | Treeview/master-detail |
| TD-011 | Feature timers | Duplicate refresh | CPU and ordering overhead | P1 | Coalesced UI updater |
| TD-012 | `ui/tag_manager.py` | Monolithic | Reuse and maintenance cost | P1 | Extract services |
| TD-013 | `ui/project_config.py` | UI-aware persistence | Blocks headless runtime | P1 | Project aggregate/contributors |
| TD-014 | Types/brands | Scattered string rules | Cross-cutting extensions | P1 | Capability registry |
| TD-015 | `core/tag_runtime.py` | Sync every scan | O(n) allocation | P1 | Definition generation |
| TD-016 | Trends | Full redraw and Tk sampling | CPU/memory/timing distortion | P1 | Trend service and line reuse |
| TD-017 | Error handling | Exceptions become `None` | Poor diagnostics/policy | P1 | Typed results/errors |
| TD-018 | `requirements.txt` | Unpinned dependencies | Non-reproducible builds | P1 | Lock/constraints |
| TD-019 | Repository | No CI | Platform regressions | P1 | Linux/Windows workflows |
| TD-020 | Logging | No rotation | Disk growth | P1/P2 | Rotating handler |
| TD-021 | Settings | No top-level schema version | Migration complexity | P2 | Version settings |
| TD-022 | Storage | Source paths depend on CWD/repo | Portability | P2 | Canonical user paths |
| TD-023 | CSV/Project | No size limits | Local resource exhaustion | P2 | Input limits |
| TD-024 | Plugins | Arbitrary imports/no SDK | Security and compatibility | P1 before enablement | Manifest/lifecycle/isolation |
| TD-025 | Documentation | Broken `build/README.md` reference | Onboarding friction | P3 | Correct link/content |
| TD-026 | UI text | Mixed languages | Inconsistent UX | P3 | String catalog/i18n |
| TD-027 | Templates | Duplicate Siemens files | Drift | P3 | Canonical template source |
| TD-028 | Private helpers | Imported across modules | Fragile refactors | P2 | Public application interfaces |
| TD-029 | Multi-PLC | Single active session model | Blocks future scope | P2 | Session manager |
| TD-030 | Internal Simulator | Limited fault/time model | Scenario limitations | P2 | Virtual clock/fault injection |

---

# 30. Recommended Target Architecture

## 30.1 Architectural direction

The recommended Version 3 architecture is a modular monolith with explicit ports and adapters. It should not begin as microservices. A single process remains appropriate for the desktop application, but domain and application layers should be independent of Tk.

```text
┌───────────────────────────────────────────────────────────────┐
│ Presentation                                                  │
│ Tk Desktop | Future Web | REST | CLI                         │
└──────────────────────────────┬────────────────────────────────┘
                               │ commands / queries / events
┌──────────────────────────────▼────────────────────────────────┐
│ Application                                                   │
│ RuntimeController | FeedbackService | AlarmService           │
│ ProjectService | RecipeService | ScenarioService             │
└──────────────────────────────┬────────────────────────────────┘
                               │ domain ports
┌──────────────────────────────▼────────────────────────────────┐
│ Domain                                                        │
│ Tag | RuntimeValue | Feedback | Alarm | Recipe | Scenario    │
│ IDs | state machines | policies | validation                 │
└──────────────────────────────┬────────────────────────────────┘
                               │ interfaces
┌──────────────────────────────▼────────────────────────────────┐
│ Infrastructure                                                │
│ PLC adapters | Project store | CSV | Settings | History      │
│ OPC UA | MQTT | Plugin host | Logging                        │
└───────────────────────────────────────────────────────────────┘
```

## 30.2 Components to introduce

Suggested conceptual packages:

```text
domain/
    tags.py
    runtime.py
    feedback.py
    alarms.py
    recipes.py
    scenarios.py

application/
    commands.py
    events.py
    event_bus.py
    tag_repository.py
    runtime_engine.py
    feedback_engine.py
    alarm_engine.py
    project_service.py

infrastructure/
    drivers/
        base.py
        registry.py
        siemens.py
        modbus.py
    persistence/
        project_store.py
        settings_store.py
    csv/
    history/

presentation/
    tk/
```

These directories do not need to appear in one rewrite. Existing modules can progressively delegate to them.

## 30.3 Migration strategy

Use a strangler approach:

1. Add pure domain component.
2. Add adapter around existing state.
3. Route one existing feature through it.
4. Preserve old public function entry points.
5. Add tests for both paths.
6. Remove duplicated legacy logic only after verification.

## 30.4 Components to divide

- `PLCSimulator` → composition root plus controllers.
- `PLCService` → registry, session, polling, adapters, diagnostics.
- `tag_manager.py` → view, repository, validation, addresses, CSV.
- `project_config.py` → store, schema/migrations, contributors, UI adapter.
- `trend_tab.py` → sampling/history, configuration, rendering.
- `alarm_tab.py` → engine and view.
- `feedback_tab.py` → engine and view.

## 30.5 Patterns to avoid

- one `after()` callback per tag/feedback/alarm;
- worker threads configuring widgets;
- another large service with all feature logic;
- a generic event bus carrying untyped dictionaries only;
- changing all public APIs at once;
- forcing every protocol into identical low-level methods;
- storing runtime values in projects;
- introducing distributed services before a clean local application layer exists.

---

# 31. Feedback Engine V2 Readiness

## 31.1 Readiness verdict

The repository is **partially ready**. It has the runtime cache, tag database, scheduling discipline, persistence safeguards, scalable UI patterns, and testing culture required to support Feedback Engine V2. It lacks the domain and event boundaries needed to implement the engine safely.

## 31.2 Required preconditions

1. Define a pure Feedback state machine.
2. Define command and feedback tag references.
3. Define behavior for missing/BAD quality.
4. Define clock and timeout semantics.
5. Define immutable identity.
6. Define engine events.
7. Define persistence contribution and migration.
8. Build a scalable master-detail Feedback view.
9. Add performance tests for thousands of definitions.
10. Keep engine evaluation independent of Tk.

## 31.3 Suggested model

```text
FeedbackDefinition
    id
    name
    command_tag_id
    feedback_tag_id
    expected_policy
    inverted
    activation_delay_ms
    timeout_ms
    reset_delay_ms
    severity
    enabled

FeedbackRuntime
    state
    command_value
    feedback_value
    quality
    activated_at
    deadline
    acknowledged
    last_transition
    diagnostic
```

Suggested states:

```text
DISABLED
IDLE
WAITING
MATCHED
MISMATCH
TIMEOUT
BAD_QUALITY
ACKNOWLEDGED
```

## 31.4 Suggested module boundaries

```text
core/feedback_model.py
services/feedback_engine.py
ui/feedback_view_model.py
ui/feedback_tab.py
tests/test_feedback_engine.py
tests/test_feedback_persistence.py
tests/test_feedback_performance.py
```

The exact paths may evolve, but the separation should remain.

## 31.5 Primary implementation risks

| Risk | Consequence | Mitigation |
|---|---|---|
| Implementing state in widgets | Untestable and fragile engine | Pure state machine first |
| Name-based references only | Broken relations on rename | Stable IDs and migration |
| Treating missing value as false | False normal/mismatch results | Explicit BAD quality state |
| Timer per feedback | Poor 5,000-item scalability | One scheduler/change-driven engine |
| Persisting runtime state | Stale project behavior | Persist definitions only |
| Direct PLC writes in engine | Tight coupling and safety risk | Command service port |
| Updating UI from worker | Tk crashes/races | Tk-thread event adapter |
| Reusing Alarm dictionaries | Domain ambiguity | Separate definitions/runtime |
| No virtual clock | Flaky timeout tests | Injected clock |
| Schema change without migration | Legacy project failure | Versioned optional section |

## 31.6 Definition of architectural readiness

Feedback Engine V2 should be considered architecturally ready when:

- the engine runs without importing Tk;
- transitions are deterministic under an injected clock;
- BAD quality is explicit;
- no callback or widget is allocated per feedback definition;
- project loading remains backward compatible;
- runtime updates can be evaluated from change sets;
- 5,000 definitions meet an agreed evaluation budget;
- the UI can be destroyed with callbacks pending without errors;
- engine and UI tests are separate;
- existing Feedback monitor behavior remains available through an adapter.

---

# Executive Scorecard

| Category | Score (0–10) | Summary |
|---|---:|---|
| Arquitetura | 6.4 | Sound core with application/UI coupling |
| Organização | 6.0 | Clear top-level layout; oversized UI modules |
| Escalabilidade | 6.2 | Strong modern tabs; weak Feedback/Alarm paths |
| Performance | 7.0 | Documented 5,000-tag improvements; Tk-thread I/O risk |
| Modularidade | 5.4 | Useful modules but implicit shared state and cycles |
| Testabilidade | 7.5 | Broad headless suite and pure helper coverage |
| Documentação | 6.8 | Strong feature docs with some drift and missing operational detail |
| UX | 7.0 | Capable modern tables; inconsistent older tabs/language |
| Manutenibilidade | 5.8 | High regression protection but central modules are costly to change |
| Preparação para Feedback Engine V2 | 5.5 | Good foundations; domain/event layer required first |

**Overall score:** **6.4/10**

---

# Top 20 Melhorias

| Rank | Improvement | Priority | Expected benefit |
|---:|---|---:|---|
| 1 | Move cyclic PLC reads off the Tk thread | P0 | Prevent UI freezes and enable controlled cancellation |
| 2 | Create a pure Feedback Engine domain/state machine | P0 | Safe foundation for Feedback Engine V2 |
| 3 | Introduce batched runtime change sets and event dispatch | P0 | Remove redundant polling and direct UI calls |
| 4 | Break the UI import cycle | P0 | Stable module boundaries and easier testing |
| 5 | Split `PLCSimulator` into explicit controllers | P0 | Reduce god-object coupling |
| 6 | Define driver session/capability contracts | P1 | Simplify new protocol support |
| 7 | Split `PLCService` into registry, session, polling, and adapters | P1 | Improve SRP and Open/Closed compliance |
| 8 | Introduce `TagRepository` and indexed lookups | P1 | Better performance and identity management |
| 9 | Add immutable tag IDs with backward-compatible migration | P1 | Safe rename, recipes, scenarios, multi-client |
| 10 | Replace Feedback per-row widgets with master-detail Treeview | P1 | Scale to thousands of feedbacks |
| 11 | Replace Alarm per-row widgets and dict model | P1 | Correct semantics and scalability |
| 12 | Coalesce Dashboard/Feedback/runtime refreshes | P1 | Reduce CPU and widget churn |
| 13 | Extract project storage/schema from Tk application | P1 | Headless runtime and safer feature growth |
| 14 | Extract CSV/vendor importers from Tag Manager | P1 | Reuse, testing, REST/plugin readiness |
| 15 | Introduce typed runtime/driver error results | P1 | Better retry, diagnostics, UX, and alarms |
| 16 | Decouple Trend sampling/history from chart rendering | P1 | Accurate timing and scalable history |
| 17 | Pin dependencies and publish tested constraints | P1 | Reproducible builds |
| 18 | Add Linux and Windows CI including packaged smoke tests | P1 | Prevent platform regressions |
| 19 | Version the complete settings schema | P2 | Predictable preference migration |
| 20 | Add log rotation and user-state log paths | P2 | Operational reliability |

---

# Top 10 Quick Wins

1. **Cache tags by normalized name** rather than repeatedly scanning `app.tags`.
2. **Cache brand compatibility and parsed addresses** until the tag-definition generation changes.
3. **Avoid `RuntimeTagCache.sync()` when definitions are unchanged.**
4. **Remove duplicate Feedback refreshes** between the cyclic read and Feedback timer.
5. **Coalesce Dashboard refresh requests** into one pending scheduled update.
6. **Use a rotating log handler** with bounded retention.
7. **Centralize supported-brand constants and capabilities.**
8. **Introduce string-compatible enums** for tag type and direction while preserving serialization.
9. **Add explicit CSV/project size limits** and tests.
10. **Correct documentation drift**, including the missing `build/README.md` reference and duplicated template guidance.

---

# Roadmap Arquitetural

## Curto prazo

**Indicative horizon: 0–3 months**

1. Establish Feedback Engine V2 domain definitions and state transitions.
2. Add an injected clock and deterministic timeout tests.
3. Introduce runtime change sets and a small typed event dispatcher.
4. Move PLC polling to a worker with a bounded result queue.
5. Add thread-safe runtime snapshot publication.
6. Replace Feedback UI with a bounded Treeview/master-detail design.
7. Add comprehensive Feedback tests, including 5,000 definitions.
8. Correct Alarm BAD-quality semantics.
9. Add dependency constraints/lock process.
10. Add initial Linux CI.

### Short-term completion criteria

- No PLC network operation blocks Tk.
- Feedback Engine imports no Tk modules.
- Runtime changes are delivered in batches.
- Feedback UI creates no widget per feedback definition.
- Legacy projects open unchanged.
- Existing public APIs remain operational.

## Médio prazo

**Indicative horizon: 3–8 months**

1. Introduce driver protocols and capability registry.
2. Split `PLCService` into session, polling, adapter, and diagnostics components.
3. Introduce `TagRepository` and stable tag IDs.
4. Extract CSV and address services from Tag Manager.
5. Extract project persistence and migrations from UI.
6. Create project contributors for Alarms, Feedbacks, Trends, PID, and simulation.
7. Modernize Alarm UI and engine.
8. Extract Trend history/sampling service.
9. Add Windows CI and packaged application smoke tests.
10. Version the full user-settings schema.
11. Add typed error/result taxonomy.
12. Add log rotation and canonical user state paths.

### Medium-term completion criteria

- A new driver is registered without editing central UI/service branches.
- Projects can be parsed, migrated, and serialized without Tk.
- Tags have stable identity.
- Alarm and Feedback engines are domain services.
- Source and packaged tests run on Linux and Windows CI.

## Longo prazo

**Indicative horizon: 8–18 months**

1. Establish a fully headless application runtime.
2. Add Recipe and Scenario domains.
3. Add OPC UA through the driver/capability architecture.
4. Add MQTT publishing/subscription through application events.
5. Introduce REST and WebSocket adapters.
6. Define authentication, authorization, write policies, and audit events.
7. Create a versioned plugin manifest and SDK.
8. Evaluate process isolation for untrusted plugins.
9. Add multi-session and multi-PLC support.
10. Prototype a Web Runtime consuming the same application APIs.
11. Add historian storage adapters.
12. Evaluate distributed simulation with stable IDs, event sequencing, and clock synchronization.

### Long-term completion criteria

- Desktop, REST, and Web adapters consume the same application layer.
- PLC transports are replaceable infrastructure adapters.
- Plugin extensions depend on stable SDK ports rather than `PLCSimulator` internals.
- Multiple sessions can operate without shared mutable driver state.
- Distributed or multi-client operation has explicit consistency and authorization rules.

---

# 36. Conclusion

PLC Universal Simulator is a credible and mature desktop simulator with an increasingly strong technical foundation. Its runtime cache, transactional persistence, address validation, scalable modern tables, shutdown handling, broad tests, and cross-platform packaging provide a reliable base for continued development.

The architecture's limiting factor is centralization rather than lack of engineering quality. `PLCSimulator`, `PLCService`, and the largest UI modules have accumulated responsibilities because the application grew successfully around a simple shared-object model. That model remains workable for incremental desktop features but is approaching its limit for domain-heavy functionality and platform expansion.

Feedback Engine V2 should become the first deliberately separated domain engine. Implementing it as pure state and policy logic, driven by runtime changes and observed by a scalable UI, will produce immediate value and establish the pattern required for Alarms, Recipes, Scenarios, OPC UA, MQTT, REST, plugins, and future web or distributed runtimes.

The recommended strategy is not a rewrite. It is a staged transition from a procedural shared-application architecture to a modular monolith with explicit domain, application, presentation, and infrastructure boundaries. Compatibility adapters, existing file formats, tested behavior, and current desktop workflows should remain in place throughout that transition.

**Final assessment:** The project is ready to continue, provided that Feedback Engine V2 begins with its architectural prerequisites rather than extending the current widget-level Feedback implementation directly.
