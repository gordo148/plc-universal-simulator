# PLC Universal Simulator — Comprehensive Repository Metrics & Architecture Audit

## Document status

| Field | Value |
|---|---|
| Purpose | Technical baseline before Feedback Engine V2 |
| Audit date | 2026-07-17 |
| Scope | Entire repository: source, tests, documentation, scripts, packaging and assets |
| Method | Read-only inspection, AST metrics, import-graph analysis and architectural review |
| Exclusions | No build, application execution, test run, formatting, source edit, commit or push |
| Companion documents | `docs/CODE_METRICS_SUMMARY.md`, `docs/CODE_METRICS_TABLES.md`, `docs/ARCHITECTURE_GRAPH.md`, `docs/REFACTORING_PLAN.md` |

## Contents

1. [Executive summary](#1-executive-summary)
2. [Repository baseline](#2-repository-baseline)
3. [Architecture and data flow](#3-architecture-and-data-flow)
4. [Code organization and dependencies](#4-code-organization-and-dependencies)
5. [Data models and persistence](#5-data-models-and-persistence)
6. [Runtime, events and concurrency](#6-runtime-events-and-concurrency)
7. [User interface](#7-user-interface)
8. [Feature reviews](#8-feature-reviews)
9. [Drivers and protocol extensibility](#9-drivers-and-protocol-extensibility)
10. [Performance and scalability](#10-performance-and-scalability)
11. [Build, versioning and packaging](#11-build-versioning-and-packaging)
12. [Logging, settings and error handling](#12-logging-settings-and-error-handling)
13. [Security review](#13-security-review)
14. [Testing and delivery readiness](#14-testing-and-delivery-readiness)
15. [Quality principles scorecard](#15-quality-principles-scorecard)
16. [Top 30 issues](#16-top-30-issues)
17. [Future-capability readiness](#17-future-capability-readiness)
18. [Recommendations and conclusion](#18-recommendations-and-conclusion)

# 1. Executive summary

The PLC Universal Simulator is a capable, test-conscious desktop simulator with broad PLC support, mature project compatibility work and a substantially improved Dashboard. Its architecture is best described as a modular monolith whose composition root, runtime coordinator and much of its application state reside in `ui/main_window.py`. Domain-oriented modules exist, but the UI remains the integration bus.

The strongest evidence is the disciplined project staging/migration path in `ui/project_config.py`, explicit tag definition/runtime separation in `core/tag_model.py` and `core/tag_runtime.py`, protocol-specific driver modules, incremental table updates, safe generated build metadata, and a sizeable test corpus. These are valuable foundations.

The highest risk is synchronous protocol scanning reachable from Tk scheduling in `ui/main_window.py:803-826`. A slow PLC call can therefore block the interface. The second structural risk is the absence of a single event/subscription layer: Dashboard, Feedbacks, Alarms, Trends and simulation perform independent scans or callbacks over shared mutable state. That design is understandable at current scale but becomes expensive and race-prone as Feedback Engine V2, APIs or multi-client features arrive.

**Overall architecture score: 6.4/10.** The product is maintainable for incremental desktop development, but Feedback Engine V2 should be preceded by a stable tag identity, a UI-independent runtime event boundary and off-thread bounded PLC I/O.

## Principal strengths

- Clear top-level areas: `core/`, `drivers/`, `services/`, `ui/`, `tests/`, `scripts/` and `packaging/`.
- Backward-compatible project migration with staging and rollback.
- Definition/runtime distinction for tags and a useful pure Dashboard model.
- Incremental Dashboard/Digital/Analog update paths instead of unconditional rebuilds.
- Protocol-specific modules for Siemens, Schneider, Modbus, Omron, Rockwell and internal simulation.
- Static version adapter with generated, ignored build metadata.
- 41 test files, 295 statically discovered test definitions and a previously verified 460-test baseline.
- Detailed product and implementation documentation.

## Principal weaknesses

- `PLCSimulator` is a 1,118-line, 71-method application god object and service locator.
- `PLCService` combines protocol dispatch, conversion, scanning, caching and error policy.
- Blocking I/O can execute through the Tk callback path.
- Six UI modules form a circular-import component.
- Multiple feature pollers repeatedly scan the same tag population.
- Mutable tag names serve as identity in several cross-feature relationships.
- Feedback and Alarm views use per-item widgets and polling, limiting 5,000-tag scale.
- Dependencies are unpinned; no CI workflow or coverage configuration was found.

# 2. Repository baseline

The audit assessed 132 tracked files and 88 Python files. Python totals are 17,842 physical LOC and 14,882 non-blank/non-comment LOC. `ui/` contains 8,623 physical LOC (48.3%), while tests contain 5,731 LOC (32.1%). Full tables and metric definitions are in `docs/CODE_METRICS_TABLES.md`.

| Indicator | Result |
|---|---:|
| Classes | 60 |
| All function definitions | 1,149 |
| Methods | 376 |
| Import statements | 511 |
| Branch decision points | 1,916 |
| Loops/comprehensions | 581 |
| Mean function complexity | 3.25 |
| Median function complexity | 2 |
| Maximum function complexity | 46 |
| Functions above complexity 20 | 14 |

The low median indicates most callables are locally simple. Risk is concentrated in orchestration hotspots: `refresh_dashboard_table`, CSV parsing/import, project staging/application and PLC scan/write paths.

# 3. Architecture and data flow

## 3.1 Current shape

```text
main.py
  └─ ui.main_window.PLCSimulator
       ├─ creates and owns tabs/widgets
       ├─ owns shared tag/project/runtime state
       ├─ schedules after() callbacks
       ├─ coordinates project lifecycle
       ├─ calls services.PLCService
       └─ refreshes Dashboard, Digital, Analog, Trends, Alarms, Feedbacks

core models/settings/runtime
       ▲                    │
       │ shared objects     ▼
UI feature modules ── services ── drivers ── PLC/network
       │
       └─ project/CSV/settings persistence
```

The directory structure suggests layers, but dependency direction is not consistently enforced. `core/` is mostly independent. `services/` knows drivers and core models. `ui/` knows almost everything and some UI modules import other UI modules bidirectionally. There is no explicit application-service layer separating use cases from Tk.

## 3.2 Data flow

1. Project or CSV data becomes tag definitions through `ui/project_config.py` or `ui/tag_manager.py`.
2. `PLCSimulator` retains the active population and coordinates `RuntimeCache`.
3. `PLCService` dispatches reads/writes to the configured protocol driver.
4. Updated values are placed in shared runtime structures.
5. Feature tabs scan or receive callbacks and update their widgets.
6. Project saving extracts state back from application/UI structures.

This flow works, but state ownership is implicit. The application object acts as an ambient context. The absence of immutable snapshots or revisioned events makes ordering, stale values and concurrency harder to reason about.

## 3.3 Event model

The present event system is a collection of Tk `after()` schedules, widget callbacks and direct function calls. It is not a typed event bus. Connection establishment already uses a worker/queue handoff in `ui/main_window.py:380-428`, demonstrating a sound pattern, but cyclic reads at `ui/main_window.py:803-826` do not consistently preserve that boundary.

## 3.4 Desired boundary

A minimal evolution is an application runtime containing `TagRegistry`, `RuntimeStore`, `RuntimeEventStream`, `DriverManager` and domain engines. Tk controllers subscribe and render. This is incremental: existing lists and callback APIs can remain as facades until consumers migrate.

# 4. Code organization and dependencies

## 4.1 Module quality

`core/` is cohesive and relatively small. `drivers/` is separated by protocol. `services/` provides useful coordination, but `PLCService` is too broad. `ui/` contains both presentation and application/domain policy. The most significant modules are:

- `ui/tag_manager.py` — 1,951 LOC; widgets, address suggestion, multiple CSV dialects, validation and mutations.
- `ui/main_window.py` — 1,259 LOC; composition, runtime, lifecycle and shared state.
- `ui/project_config.py` — 990 LOC; strong migration/staging but UI-aware serialization.
- `services/plc_service.py` — 770 LOC; protocol facade plus scanning/conversion/cache behavior.

## 4.2 Import graph

The highest fan-out is `ui.main_window` with 19 internal dependencies. The highest fan-in is `core.tag_model` with 31 importers, appropriate for a central model, followed by `core.tag_runtime` with 21. One six-module strongly connected component exists:

```text
ui.alarm_tab, ui.analog_tab, ui.dashboard_tab,
ui.digital_tab, ui.project_config, ui.tag_manager
```

This is factual evidence of insufficient UI boundaries. It can cause import-order fragility and complicates headless tests. The solution is not a bulk move; introduce narrow controller ports and remove one cycle edge at a time.

## 4.3 Complexity and duplication

No exact normalized duplicate function bodies of meaningful size were identified by the AST heuristic. Structural duplication remains in table creation/reconciliation, scheduled scanning and tab factories. Digital and Analog tabs in particular share patterns but also have genuine domain differences; extraction should parameterize mechanics only.

Dead-code analysis is necessarily conservative because Tk callback names, imports used as monkeypatch seams and plugin loading are dynamic. `SOURCE_BUILD_TYPE` at `scripts/generate_version.py:18` is a candidate unused constant, not a confirmed safe deletion. A configured Ruff/Vulture run should be introduced before cleanup.

# 5. Data models and persistence

## 5.1 Tags

`core/tag_model.py` represents tag definition data, while `core/tag_runtime.py` represents live state. This is a good separation. The weakness is identity: names and list positions remain important across Dashboard, trends, feedbacks and project references. Since names are user-editable, rename operations can invalidate associations or require broad repair.

Recommendation: introduce an immutable tag ID with a compatibility mapping for old projects. Generate IDs while staging an old project, preserve original names and write the new field only on explicit save.

## 5.2 Dashboard

`core/dashboard_model.py` provides pure population/filter/sort behavior, while `ui/dashboard_tab.py` handles rendering and preferences. This is one of the better domain/UI splits. Column preferences are user-level rather than project-level, and updates are incremental. Remaining state and scheduling should move behind a controller/view-model boundary.

## 5.3 Projects

`ui/project_config.py` performs migration, staging, application and rollback. Its complexity—`build_project_data` complexity 30, `_stage_project_data` 30 and `_apply_project_data` 21—reflects real compatibility requirements. The behavior is strong, but it depends on UI/application attributes. Extracting a project repository and DTO layer would make migrations headless and safer.

## 5.4 CSV

`ui/tag_manager.py` supports generic, TIA and Schneider-oriented imports. Its parsers are long and branch-heavy. Files are loaded as bytes for detection/parsing without a clear input-size policy. Parsing, validation, address normalization and mutation should become a staged import service with a golden fixture corpus.

## 5.5 Settings

`core/settings.py` validates/defaults and uses atomic persistence patterns. The concern is location: source and frozen execution need a single platform user-data policy. Settings/preferences must remain outside projects, but migration from current locations should be non-destructive.

# 6. Runtime, events and concurrency

## 6.1 Main loop

Tk is the authoritative UI thread. `after()` schedules cyclic reading, refreshes, feedback scans, alarms, trends and status updates. Several callbacks correctly check lifecycle, but cancellation ownership is distributed.

## 6.2 Threads and queues

Connection setup uses a worker and queue, then hands results back to Tk. This is the correct architectural template. Protocol reads/writes need the same bounded worker ownership. UI widgets must never be accessed by workers; workers should emit immutable snapshots/events.

## 6.3 Race and lifecycle risks

- A delayed callback may target a destroyed widget unless every schedule is cancelled or guarded.
- Connection/disconnection can overlap with in-flight driver operations.
- Multiple refresh consumers may observe different points in a scan.
- Shared mutable tag/runtime structures have no explicit revision or single-writer contract.
- Shutdown logic is centralized in a 143-line `on_close`, making idempotence difficult to prove.

## 6.4 Recommended runtime contract

Use one runtime writer, bounded command and event queues, monotonic revisions and cancellation tokens. Define whether overload coalesces intermediate values or applies backpressure. Tk processes a bounded number of events per frame and renders only changed cells/panels.

# 7. User interface

The desktop UI is feature-rich and consistent with the simulator’s audience. CustomTkinter and ttk are combined pragmatically. Dashboard v2 offers filters, column management, sorting, compact mode, side-panel details and incremental updates.

The main weakness is the fusion of widget construction, state and business orchestration. Large factory functions—`create_tag_manager_tab` (230 LOC), `create_dashboard_tab` (133) and `create_trend_tab` (132)—are difficult to test without Tk. `PLCSimulator` exposes many mutable attributes that tabs consume directly.

For scalability, Treeview-based tables are preferable to per-row widget frames. Feedback and Alarm screens should adopt virtualization or a master-detail table. Selection, focus and scroll must be keyed by stable ID and retained during incremental reconciliation.

# 8. Feature reviews

## 8.1 Dashboard

**Facts.** `ui/dashboard_tab.py` updates cells incrementally and delegates filtering/sorting to `core/dashboard_model.py`. `refresh_dashboard_table` is the most complex function (46). User column preferences and compact/full layouts are persisted outside projects.

**Assessment.** Functionally mature and comparatively well tested. Remaining risk is controller complexity and repeated population scans. Preserve its incremental design while extracting state/filter/sort orchestration.

## 8.2 Digital simulation

**Facts.** `ui/digital_tab.py` has an incremental visible-row path; `refresh_digital_visible_rows` is 95 LOC, complexity 28. It relies on shared application/runtime state.

**Assessment.** Good performance intent, but reconciliation mechanics are complex. Share a tested generic row reconciler with Analog only after current behavior is characterized.

## 8.3 Analog simulation

**Facts.** `ui/analog_tab.py` is 764 LOC; its main row refresh is 107 LOC and complexity 31. `services/analog_simulation.py` contains a substantial manager, and `ui/analog_profiles.py` normalizes profiles.

**Assessment.** Better domain support than a purely widget-based implementation, but configuration, profile UI and runtime updates still cross layers. Define analog commands/events and isolate scale/unit conversion.

## 8.4 Trend Engine

**Facts.** Sampling and Matplotlib rendering are coordinated from `ui/trend_tab.py`. Chart redraws are broad and historical buffers need explicit resource limits.

**Assessment.** Suitable for desktop projects of moderate size. It is not yet a headless trend engine. Separate bounded time-series storage, sampling policy and rendering.

## 8.5 Alarm Engine

**Facts.** `ui/alarm_tab.py` scans at a fixed interval and creates item-level UI. Missing/BAD values can flow to a non-active visual state around `ui/alarm_tab.py:236-275`.

**Assessment.** The semantics of inactive versus unknown/bad quality need explicit separation. Alarm evaluation, lifecycle, acknowledgement and history should become a domain service before external APIs.

## 8.6 Feedback System

**Facts.** `ui/feedback_tab.py` couples configuration, periodic evaluation and row widgets. Feedback-related updates overlap with the main cyclic runtime path.

**Assessment.** This is the highest-priority domain redesign. V2 needs deterministic rule evaluation, stable IDs, conflict/loop handling, quality propagation, diagnostics and an event source independent of Tk.

## 8.7 Tag Manager

**Facts.** `ui/tag_manager.py` is the largest module and owns tag UI, address generation, CSV dialects, validation and mutations.

**Assessment.** High regression surface. Extract parser/validator/import transaction and registry commands incrementally; keep the existing UI callbacks as adapters.

## 8.8 Project persistence

**Facts.** Migration, stage, apply and rollback logic is substantial and tested. Old projects are a first-class concern.

**Assessment.** Behavior is a strength; placement is the issue. Move unchanged semantics into a UI-free repository and preserve golden round-trip fixtures.

## 8.9 CSV import/export

**Facts.** Multiple industrial dialects are supported and existing behavior is compatibility-sensitive. Parsing is branch-heavy and file size is not explicitly bounded.

**Assessment.** Preserve dialect adapters, introduce a normalized intermediate representation, size/encoding limits and transactional application.

## 8.10 Settings and preferences

**Facts.** Preferences have validation/default behavior and Dashboard settings are user-owned. Atomic writing is used.

**Assessment.** Add schema versioning and one user-data path service. Opening a project must never change user layout.

## 8.11 Plugin architecture

**Facts.** `core/plugin_loader.py` loads explicitly configured Python modules and exposes a minimal `Plugin` abstraction. There is no formal manifest, compatibility range, permission model, isolation or lifecycle contract.

**Assessment.** This is an internal extension hook, not a public SDK. A Plugin SDK should wait for stable application-service and driver/event APIs.

# 9. Drivers and protocol extensibility

## 9.1 Supported adapters

The repository contains modules for Siemens, Schneider, Modbus, Omron, Rockwell and an internal simulator. Siemens address parsing is separated, which is positive. Drivers differ in connection models, address forms, read/write shapes and error behavior.

## 9.2 Extensibility assessment

Adding a driver is possible, but it requires changes across `drivers/`, `services/plc_service.py`, connection UI/configuration, project persistence, status handling and tests. This is cross-cutting rather than plug-in.

A protocol interface should define lifecycle, scalar/batch reads, scalar/batch writes, timeout/cancellation, quality/error mapping and capabilities. Vendor-specific functionality should be expressed through capability protocols, not forced into a lowest-common-denominator base class.

## 9.3 Driver-specific observations

- **Siemens:** mature integration and separate address logic; complex scan path (`_scan_siemens`, complexity 20, nesting 10) deserves decomposition and batch-plan tests.
- **Schneider:** dedicated driver and import support; ensure address normalization has one source of truth.
- **Modbus:** common protocol, but connection/register capabilities should be explicit.
- **Omron/Rockwell:** dedicated adapters exist; require simulator/HIL contract coverage.
- **Internal simulator:** valuable deterministic test adapter; expand it to implement the exact common contract.

# 10. Performance and scalability

## 10.1 Complexity profile

No definitive O(n²) defect was proven statically. The dominant risk is additive repeated O(n) work: independent Dashboard, Feedback, Alarm and other refresh cycles scan the same population. Sorting adds O(n log n) when relevant. At 5,000 tags, multiple scans plus thousands of widget operations can exceed the UI frame budget even when each loop is individually linear.

## 10.2 UI responsiveness

The critical risk is protocol latency on the Tk path. Next are bulk CSV/project processing and Matplotlib redraws. Performance work should measure UI event-loop latency, not only total operation time.

## 10.3 Memory

Potential growth sources are trend histories, retained widget references, pending callbacks and full-file CSV buffers. Explicit bounds and lifecycle tests are required. No static evidence establishes an active leak, so this is a risk requiring profiling rather than a factual leak claim.

## 10.4 Cache opportunities

- Maintain tag indexes by stable ID, name, type/source and feature flags.
- Increment filter populations by revision instead of rescanning all definitions.
- Compile driver batch plans when definitions change, not each cycle.
- Store Dashboard sort keys and invalidate only affected rows.
- Share one runtime event with Dashboard, Trends, Alarms and Feedbacks.

## 10.5 Performance acceptance baseline

Use 100, 1,000, 2,000 and 5,000 tags; measure load, refresh p50/p95/p99, Tk heartbeat delay, CPU, RSS and queue depth. Run idle, active-value churn, sorting/filtering, connect/disconnect and one-hour soak scenarios.

# 11. Build, versioning and packaging

The version architecture uses static `core/version.py` as a compatibility adapter and optional generated `core/generated/build_metadata.py`, ignored by Git. Build scripts calculate Git-derived metadata without rewriting the tracked adapter. `SOURCE_DATE_EPOCH` and commit timestamps support reproducible build dates, with current time as a final fallback.

PyInstaller specifications and Linux/Windows scripts form the packaging path; installers copy the built artifact. This is a sound direction. Remaining risks are unpinned dependencies, lack of automated cross-platform artifact tests, environmental PyInstaller differences and absence of a CI release matrix.

Required artifact checks: source and binary report consistent About/version values; two builds from the same commit produce the same semantic metadata; build leaves tracked status unchanged; builds without `.git` use a documented fallback; installed settings/log paths are writable.

# 12. Logging, settings and error handling

Logging exists across runtime and protocol paths, but rotation and structured context are limited. Every protocol failure should include adapter, connection, operation, tag ID/name and address without exposing secrets. Logs should be stored under a platform user-data directory.

Error handling is generally defensive. Broad exception boundaries are appropriate around UI callbacks and vendor libraries, but domain services should raise typed errors. UI code should translate stable error categories to user messages while retaining exception chains in logs.

Settings should have schema versions, atomic writes, corruption fallback and explicit migrations. Environment-specific data must not be colocated with installed executables or tracked source.

# 13. Security review

This is a desktop simulator, not an internet service, but it processes untrusted project/CSV/plugin paths and communicates with industrial endpoints.

- Project and CSV inputs need size, depth, count and value-length limits.
- Paths should be normalized and validated before read/write.
- Plugin loading executes Python code with application privileges; a future SDK requires explicit trust and capability policy.
- Future MQTT/REST/OPC UA work requires credentials, certificate storage, authentication, authorization and audit logging.
- Error dialogs/logs should avoid leaking secrets or full connection strings.
- Driver timeouts and bounded queues are also availability controls.

No claim of an exploitable vulnerability is made from static inspection alone. These are trust-boundary gaps to address before network-facing features.

# 14. Testing and delivery readiness

The repository has 41 test files and 295 statically named tests. A previously verified project baseline records 460 passing tests, but this audit intentionally ran none. No instrumented coverage result, coverage configuration or CI workflow was found.

Strengths include project compatibility, Dashboard behavior and core model tests. Weak areas are real Tk lifecycle, driver disconnect races, hardware/simulator contract matrices, feedback/alarm semantics, soak/performance, malicious inputs and installed Windows artifacts.

CI should start with existing tests, `compileall`, import-cycle checks and artifact-free linting. Then add coverage reporting, Linux GUI tests under a virtual display, protocol simulator tests and Windows packaging smoke tests. Do not begin with brittle coverage gates; establish the baseline and ratchet it.

# 15. Quality principles scorecard

| Principle | Score | Evidence-based assessment |
|---|---:|---|
| SOLID overall | 5.6/10 | SRP/DIP violations cluster in `PLCSimulator`, `PLCService` and UI feature modules. |
| Single Responsibility | 4.8/10 | Main window, tag manager and project config each combine several change reasons. |
| Open/Closed | 5.5/10 | New drivers/features require edits across central dispatch and UI. |
| Liskov Substitution | 6.5/10 | Limited inheritance; driver contracts are mostly implicit. |
| Interface Segregation | 5.8/10 | Capability-specific interfaces are missing. |
| Dependency Inversion | 4.8/10 | UI/orchestrator depends directly on concrete services and modules. |
| DRY | 5.8/10 | Repeated table/polling structures; no exact body duplication found. |
| KISS | 6.4/10 | Direct desktop model is understandable, but central objects accumulate complexity. |
| Separation of Concerns | 5.5/10 | Models are separated in places; UI owns persistence/runtime policy elsewhere. |
| Composition over Inheritance | 7.2/10 | Composition is common and inheritance shallow. |
| Encapsulation | 5.7/10 | Shared mutable application attributes form an ambient service locator. |
| Testability | 6.8/10 | Large test corpus and pure models, offset by Tk/global-state coupling. |
| Maintainability | 6.0/10 | Reasonable local code; hotspots and cycles make broad changes expensive. |

# 16. Top 30 issues

Each row distinguishes observed evidence from the recommended action.

| # | Description | Evidence | Impact | Priority | Effort | Recommendation | Risk if ignored |
|---:|---|---|---|---|---|---|---|
| 1 | PLC I/O can block Tk | `ui/main_window.py:803-826` schedules cyclic reads reaching `PLCService` | Frozen UI and delayed shutdown | Critical | M | Bounded worker, immutable snapshots, Tk event drain | Production hangs on slow/disconnected PLC |
| 2 | Application god object | `PLCSimulator`, 1,118 LOC/71 methods | High coupling and regression radius | Critical | L | Extract registry, runtime, lifecycle and repositories incrementally | Feedback V2 compounds central complexity |
| 3 | No typed runtime event layer | Features use callbacks/pollers/shared state | Redundant scans and inconsistent snapshots | Critical | L | Revisioned runtime event stream | APIs/engines become tightly coupled to Tk |
| 4 | Mutable names act as identity | Cross-feature tag references are name-oriented | Rename fragility and ambiguous references | Critical | M | Immutable tag IDs with old-project migration | Rules/trends/alarms silently detach |
| 5 | Feedback logic is UI-coupled | `ui/feedback_tab.py` owns scan/widgets/config behavior | V2 is hard to test or scale | High | L | Headless deterministic engine and subscribed view | Loops/conflicts and scale defects |
| 6 | `PLCService` has too many roles | 619 LOC/22 methods, aggregate complexity 136 | Protocol changes affect runtime core | High | M | Split adapter dispatch, batch planning, conversion and cache | New protocols increase branching |
| 7 | Six-module UI import cycle | Confirmed SCC in import graph | Import-order fragility, hard isolation | High | M | Controller ports; remove edges one at a time | Circular failures and difficult refactors |
| 8 | Independent O(n) pollers | Dashboard/Alarm/Feedback/Trend schedules | CPU/widget work multiplies at scale | High | L | Shared change subscriptions | 5,000-tag responsiveness degrades |
| 9 | Per-item Feedback widgets | `ui/feedback_tab.py` row presentation | Widget/memory scaling pressure | High | M | Virtualized Treeview/master-detail | Large feedback projects become unusable |
| 10 | Per-item Alarm widgets/polling | `ui/alarm_tab.py` | Update overhead and state ambiguity | High | M | Domain alarm engine + virtualized view | Missed/late alarm UX |
| 11 | Alarm BAD state can look inactive | `ui/alarm_tab.py:236-275` | Operators may infer normal state | High | S | Explicit UNKNOWN/BAD state and tests | Misleading operational display |
| 12 | Trend redraw/storage coupling | `ui/trend_tab.py` coordinates sampling/rendering | UI latency and memory growth | High | M | Bounded store and incremental renderer | Long sessions degrade or exhaust memory |
| 13 | Tag Manager mixes five concerns | `ui/tag_manager.py`, 1,951 LOC | Highest change/regression surface | High | L | Extract CSV, validation, registry commands | Import/driver changes destabilize UI |
| 14 | Project persistence is UI-aware | `ui/project_config.py`, complex stage/apply | Hard headless/API reuse | High | M | UI-free project repository preserving staging | Web/REST must import UI |
| 15 | CSV reads are not explicitly bounded | Whole-file byte parsing paths | Memory/availability risk | High | S | Size/count/string limits and streaming where useful | Large/malicious input stalls process |
| 16 | Callback lifecycle is distributed | Multiple independent `after()` loops | Destroyed-widget exceptions/leaks | High | M | Central schedule registry and cancellation tokens | Intermittent shutdown/project-close errors |
| 17 | Shutdown is monolithic | `PLCSimulator.on_close`, 143 LOC | Hard to prove idempotence/bounds | High | M | Shutdown coordinator with ordered phases | Hangs and orphan workers/resources |
| 18 | Dependencies are unpinned | `requirements.txt` entries have no versions | Non-reproducible environments/builds | High | S | Tested constraints/lock files | Same commit behaves differently later |
| 19 | No CI workflow found | No repository workflow configuration | Regressions rely on local discipline | High | S | Linux test/compile/lint CI, then Windows build | Broken main branch/release |
| 20 | Coverage is unknown | No coverage config/result | Blind spots cannot be quantified | Medium | S | Publish coverage baseline and ratchet | False confidence from test counts |
| 21 | Driver interface is implicit | New adapters require cross-cutting edits | Slow protocol expansion | High | M | Capability-based adapter contract | OPC UA/MQTT duplicate orchestration |
| 22 | Driver timeout/error policy varies | Vendor libraries differ | Inconsistent recovery and UX | High | M | Common bounded lifecycle/error mapping | Stalls and vendor-specific regressions |
| 23 | Settings/log paths need one policy | Source/frozen paths handled separately | Write failures and scattered user data | Medium | M | Platform user-data path service/migration | Installed-mode failures |
| 24 | Logs are not clearly bounded | No common rotation policy | Disk growth over long runs | Medium | S | Rotating structured logs | Disk exhaustion/poor diagnostics |
| 25 | Runtime cache requires repeated reconciliation | Population sync scans | Avoidable O(n) work | Medium | M | Registry revisions and indexed updates | Scale cost grows across consumers |
| 26 | Dashboard refresh is highly complex | `refresh_dashboard_table`, complexity 46 | Fragile feature evolution | Medium | M | Extract controller/diff planner, retain incremental renderer | Column/filter changes regress selection/scroll |
| 27 | Analog/Digital reconciliation repeats | Complex refreshes 31 and 28 | Duplicate fixes and test burden | Medium | M | Shared tested reconciliation primitive | Divergent behavior and bugs |
| 28 | Plugin loader is not a public SDK | No manifest/version/permission/isolation | Unsafe extension expectations | Medium | L | Defer SDK; define lifecycle/capabilities | Third-party plugins depend on internals |
| 29 | Static hygiene tooling absent | Ruff/Vulture/Radon unavailable/config absent | Dead imports/complexity drift | Medium | S | Add check-only tools with baseline | Gradual quality erosion |
| 30 | Cross-platform artifacts lack automated smoke tests | Scripts/specs exist, no CI matrix | Packaging regressions discovered late | Medium | M | Build/install/About smoke tests on Linux/Windows | Release failures and version mismatch |

# 17. Future-capability readiness

| Capability | Readiness | Supporting assets | Blocking gaps |
|---|---:|---|---|
| Feedback Engine V2 | 5/10 | Existing feedback UX/project data/runtime cache | Stable IDs, events, deterministic engine, loop/conflict policy |
| Dashboard V3 | 7/10 | Strong v2 model/preferences/incremental table | Controller extraction and shared runtime events |
| Recipes | 4/10 | Tag writes and project persistence | Transactional commands, validation, rollback, stable IDs |
| Scenario Engine | 4/10 | Internal simulation and analog manager | Virtual clock, command/event model, headless engine |
| OPC UA | 5/10 | Driver modules and connection concepts | Formal adapter/capabilities, certificates, async lifecycle |
| MQTT | 4/10 | Runtime values and logging | Event stream, topic mapping, backpressure, secrets |
| REST API | 3/10 | Some pure core models | Headless host, application services, auth/concurrency |
| Plugin SDK | 3/10 | Minimal loader | Stable API, manifests, lifecycle, compatibility/security |
| Web Runtime | 2/10 | Dashboard concepts | UI-independent runtime, API and web view models |
| Multi-client | 2/10 | Central runtime state | Server ownership, consistency, auth and conflicts |
| Distributed simulation | 2/10 | Internal simulator concepts | Event protocol, distributed clock, partition/recovery model |

# 18. Recommendations and conclusion

Do not begin with a broad rewrite. Establish safety rails, then extract one vertical runtime path. The recommended sequence is:

1. CI, dependency constraints, coverage and scale baselines.
2. Bounded off-thread PLC I/O and centralized callback lifecycle.
3. Stable tag identity and a UI-independent registry/runtime store.
4. Typed revisioned runtime events with explicit overload semantics.
5. Feedback Engine V2 as a deterministic headless consumer/producer.
6. Migrate Alarm/Trend/Dashboard views to subscriptions incrementally.
7. Extract persistence and protocol contracts before REST/plugins.

The system is **ready for continued product development with architectural preparation**, not ready for unconstrained addition of event-heavy or network-facing features. With the first four steps completed, Feedback Engine V2 can be built on a durable foundation. The detailed sequencing, quick wins, medium and major refactors, twelve-month roadmap and verification gates are in `docs/REFACTORING_PLAN.md`.

## Audit limitations

- Conclusions are based on static repository evidence; runtime and hardware behavior was not executed.
- Complexity is a standard-library AST approximation because dedicated analyzers were unavailable.
- Coverage cannot be estimated numerically without running instrumentation; qualitative gaps are identified instead.
- Dynamic imports and Tk callback registration prevent definitive dead-code declarations.
- Existing untracked `docs/SOFTWARE_ARCHITECTURE_REVIEW.md` was not created or modified by this audit.
