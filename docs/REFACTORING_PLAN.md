# PLC Universal Simulator — Prioritised Refactoring Plan

## 1. Purpose and guardrails

This roadmap converts the audit into sequenced engineering work. It does not prescribe a rewrite. Every phase preserves `.simproject` compatibility, current public imports, protocol behavior and the desktop workflow. Behavioral characterization tests precede boundary changes.

Priority meanings: **P0** blocks safe evolution; **P1** should precede Feedback Engine V2; **P2** improves medium-term scale; **P3** is strategic. Effort is **S** (days), **M** (one to three iterations), or **L** (multi-iteration).

## 2. Architectural target

```text
Tk Views / Controllers
        │ commands + immutable view models
        ▼
Application Services ───── User Preferences
        │
        ├── Tag Registry (stable IDs, definitions)
        ├── Runtime Store (values, quality, timestamp, revisions)
        ├── Event Stream / Subscriptions
        ├── Feedback Engine V2
        ├── Alarm Engine
        └── Trend Engine
                 │
        Protocol Adapter Interfaces
                 │
 Siemens | Schneider | Modbus | Omron | Rockwell | Internal
```

The target separates PLC I/O, deterministic domain processing and Tk rendering. It allows future transports—OPC UA, MQTT and REST—to consume the same runtime events without importing UI modules.

## 3. Entry criteria for Feedback Engine V2

Before implementing the engine:

1. Define stable tag identity independent of mutable display names.
2. Introduce a typed runtime-change event carrying tag ID, old/new value, quality, timestamp and revision.
3. Ensure protocol I/O never blocks the Tk thread.
4. Define feedback rule schema, validation and deterministic execution semantics.
5. Add bounded queues, lifecycle cancellation and stale-event policy.
6. Characterize existing feedback project fields for backward compatibility.
7. Establish engine unit tests independent of Tk.

## 4. Top 20 quick wins

| # | Action | Evidence | Priority | Effort | Acceptance criterion |
|---:|---|---|---|---|---|
| 1 | Add CI for Linux unit tests and compile checks | No workflow found | P0 | S | Every branch runs tests and `compileall`. |
| 2 | Publish a dependency constraints/lock strategy | `requirements.txt` is unpinned | P0 | S | Recreated environment resolves known versions. |
| 3 | Add timeout policy to every driver operation | PLC calls can stall UI/runtime | P0 | S | All adapters expose bounded timeouts. |
| 4 | Add rotating log handlers | Logs can grow without bound | P1 | S | Size/count limits are tested. |
| 5 | Move logs/settings to platform user-data paths | Frozen-path behavior is fragile | P1 | S | Source and installed runs use user-writable paths. |
| 6 | Add project and CSV size guards | Whole-file input is accepted | P1 | S | Oversized inputs fail clearly before allocation. |
| 7 | Document runtime thread ownership | Mixed Tk/background behavior | P1 | S | Each service documents allowed calling thread. |
| 8 | Add callback cancellation registry | Many independent `after()` loops | P1 | S | Closing project/window leaves no pending callback. |
| 9 | Record baseline 100/1,000/5,000-tag benchmarks | No common performance gate | P1 | S | Repeatable benchmark output is stored as CI artifact. |
| 10 | Add import-cycle check | Six UI modules form one SCC | P1 | S | New cycles fail CI; current cycle is allow-listed temporarily. |
| 11 | Add Ruff in check-only mode | No lint configuration | P1 | S | Unused imports and common defects are reported. |
| 12 | Add coverage reporting without an initial hard gate | Coverage unknown | P1 | S | CI publishes module-level coverage. |
| 13 | Define alarm quality-state tests | BAD/missing can appear normal | P1 | S | UNKNOWN/BAD semantics are explicit and tested. |
| 14 | Bound trend history per series | Long sessions risk memory growth | P1 | S | Configured cap is enforced and tested. |
| 15 | Consolidate refresh intervals as named settings | Multiple fixed poll periods | P2 | S | No feature embeds unexplained refresh constants. |
| 16 | Add structured context to driver errors | Protocol failures are hard to compare | P2 | S | Driver/tag/address/operation appear in logs. |
| 17 | Validate plugin paths and failures explicitly | Loader imports arbitrary configured files | P2 | S | Failure modes are isolated and reported. |
| 18 | Mark compatibility imports/callback seams | Static analysis false positives | P2 | S | Public/test seams are documented near definitions. |
| 19 | Add architecture decision records template | Major choices live across docs | P2 | S | New architectural changes use a standard ADR. |
| 20 | Remove only confirmed unused version constants | `SOURCE_BUILD_TYPE` candidate | P3 | S | Removal has reference scan and regression test. |

## 5. Top 20 medium refactors

| # | Refactor | Primary location | Priority | Effort | Dependency/risk control |
|---:|---|---|---|---|---|
| 1 | Extract a UI-independent `TagRegistry` | `ui/main_window.py`, `core/tag_model.py` | P0 | M | Preserve current tag list facade. |
| 2 | Introduce stable tag IDs | model/project migration | P0 | M | Generate IDs on old project load; retain names. |
| 3 | Move PLC polling to a bounded worker | `services/plc_service.py`, `ui/main_window.py` | P0 | M | Tk consumes snapshots/events only. |
| 4 | Create typed runtime events | `core/tag_runtime.py` | P0 | M | Version event schema and test ordering. |
| 5 | Centralize subscriptions and scheduling | UI tabs/main window | P1 | M | Adapter preserves existing callbacks initially. |
| 6 | Extract project repository service | `ui/project_config.py` | P1 | M | Keep migration/staging/rollback behavior. |
| 7 | Extract CSV parser/import transaction | `ui/tag_manager.py` | P1 | M | Golden corpus protects formats. |
| 8 | Split `PLCService` dispatch from protocol adapters | `services/plc_service.py` | P1 | M | Characterize every current driver call. |
| 9 | Define a protocol adapter interface | `drivers/` | P1 | M | Capability flags allow vendor differences. |
| 10 | Extract Dashboard controller/state | `ui/dashboard_tab.py` | P1 | M | Preserve incremental updates and preferences. |
| 11 | Unify digital/analog table reconciliation | `ui/digital_tab.py`, `ui/analog_tab.py` | P2 | M | Parameterize behavior, not domain semantics. |
| 12 | Build a virtualized feedback list | `ui/feedback_tab.py` | P1 | M | Maintain selection/scroll during updates. |
| 13 | Build a virtualized alarm list | `ui/alarm_tab.py` | P1 | M | Preserve acknowledgement semantics. |
| 14 | Separate trend sampling from rendering | `ui/trend_tab.py` | P1 | M | Rendering subscribes to bounded samples. |
| 15 | Create user-data path service | settings/logs/preferences | P1 | M | Migrate existing files non-destructively. |
| 16 | Add settings schema/version migration | `core/settings.py` | P2 | M | Invalid/old preferences restore safely. |
| 17 | Replace cross-tab imports with controller ports | six-module UI SCC | P1 | M | Remove one edge at a time with tests. |
| 18 | Introduce structured domain errors | services/persistence/drivers | P2 | M | UI maps stable error codes to messages. |
| 19 | Add hardware-simulator contract suites | `drivers/`, tests | P2 | M | Same tests run for every adapter. |
| 20 | Create shutdown coordinator | `PLCSimulator.on_close` | P1 | M | Idempotent cancellation and bounded joins. |

## 6. Top 20 major refactors

| # | Refactor | Strategic value | Priority | Effort | Preconditions |
|---:|---|---|---|---|---|
| 1 | Event-driven runtime kernel | Removes redundant polling; enables multiple consumers | P1 | L | Stable IDs, worker I/O, event schema |
| 2 | Feedback Engine V2 as deterministic domain service | Core requested capability | P1 | L | Runtime kernel and rule schema |
| 3 | Plugin SDK with manifests and capabilities | Safe extensibility | P2 | L | Adapter interfaces and versioned API |
| 4 | Alarm engine independent of Tk | Correct quality/state lifecycle | P2 | L | Runtime events and persistence schema |
| 5 | Trend engine independent of Matplotlib | Headless sampling/storage | P2 | L | Runtime events and bounded buffers |
| 6 | Recipe domain and transaction service | Future recipes | P2 | L | Stable IDs and validated writes |
| 7 | Scenario engine with virtual clock | Reproducible simulation | P2 | L | Feedback engine and command bus |
| 8 | OPC UA adapter | Protocol expansion | P2 | L | Driver contract/capabilities |
| 9 | MQTT adapter and topic mapping | Event integration | P2 | L | Runtime events and security config |
| 10 | REST API boundary | Headless integrations | P2 | L | Application services detached from Tk |
| 11 | Multi-client concurrency model | Shared runtime | P3 | L | Server runtime, auth and conflict policy |
| 12 | Distributed simulation coordination | Scale/out-of-process execution | P3 | L | Stable event protocol and clock semantics |
| 13 | Headless application host | CI/services/web runtime | P2 | L | Composition root outside UI |
| 14 | Web runtime/view model API | Dashboard evolution | P3 | L | Headless host and REST/WebSocket API |
| 15 | Versioned project-domain schema package | Independent migration/testing | P2 | L | Repository extraction |
| 16 | Unified table/view virtualization toolkit | 5,000+ item UX | P2 | L | Controller/view-model boundaries |
| 17 | Observability subsystem | Diagnose performance and devices | P2 | L | Structured errors/events |
| 18 | Cross-platform release pipeline | Repeatable signed artifacts | P2 | L | Locks, CI, packaging tests |
| 19 | Security model for plugins/API/secrets | Enables external interfaces safely | P2 | L | Threat model and config service |
| 20 | Remove `PLCSimulator` service-locator role | Long-term modularity | P2 | L | Incremental extraction of all above ports |

## 7. Twelve-month roadmap

### Months 1–2 — Establish safety rails

- CI, dependency constraints, coverage reporting and performance baselines.
- Driver timeout/error policy and callback lifecycle registry.
- Characterization tests for projects, CSV, drivers, feedbacks and shutdown.
- Architecture decisions for stable tag identity, event ordering and thread ownership.

**Exit:** reproducible test environment; known performance baseline; no unbounded PLC operation in UI design.

### Months 3–4 — Create runtime boundaries

- Introduce `TagRegistry` and stable IDs behind compatibility facades.
- Move PLC polling to a bounded worker and publish immutable snapshots.
- Introduce typed runtime events and centralized subscription lifecycle.
- Begin breaking the UI import cycle.

**Exit:** Tk never performs blocking network I/O; legacy projects load unchanged; event order is tested.

### Months 5–6 — Deliver Feedback Engine V2 foundation

- Define and migrate feedback rule schema.
- Implement deterministic evaluation, conflict policy, loop detection and diagnostics.
- Add engine unit, property, scale and lifecycle tests.
- Replace per-row feedback polling with subscriptions/virtualized presentation.

**Exit:** engine runs headlessly and handles 5,000-tag event workloads within agreed latency.

### Months 7–8 — Consolidate engines and persistence

- Separate alarm and trend domain engines from widgets.
- Extract project repository and CSV import services.
- Add settings schema migrations and platform user-data locations.
- Establish shared protocol adapter contract suites.

**Exit:** alarm/trend/feedback logic is independently testable; persistence is UI-free.

### Months 9–10 — Extensibility

- Define Plugin SDK manifest, compatibility and capability model.
- Prototype OPC UA and MQTT adapters against the common contract.
- Create headless composition root and read-only REST prototype.
- Threat-model external interfaces and secret storage.

**Exit:** one external protocol and one plugin load through documented stable interfaces.

### Months 11–12 — Productize and scale

- Cross-platform CI/release pipeline and installed-artifact smoke tests.
- Virtualized large-list toolkit across Dashboard, Feedbacks and Alarms.
- Soak tests, observability and resource budgets.
- Decide scope for Recipes, Scenario Engine and multi-client runtime.

**Exit:** repeatable Linux/Windows releases; 5,000-tag soak gate; versioned SDK preview.

## 8. Feature readiness and required enabling work

| Capability | Current readiness | Required work before implementation |
|---|---:|---|
| Feedback Engine V2 | 5/10 | Stable identity, event stream, deterministic rules, lifecycle and scale tests |
| Recipes | 4/10 | Transactional writes, stable IDs, validation and rollback |
| Scenario Engine | 4/10 | Virtual clock, command/event model, headless runtime |
| OPC UA | 5/10 | Adapter interface, capability model, certificate/security settings |
| MQTT | 4/10 | Event stream, topic model, reconnect/backpressure and secrets |
| REST API | 3/10 | Application-service boundary, headless host, auth and concurrency |
| Plugin SDK | 3/10 | Manifest/API versioning, isolation, permissions and lifecycle |

## 9. Migration rules

- Never rewrite a project merely because it was opened.
- Add schema fields with defaults and retain unknown fields where feasible.
- Map old name-based references to generated stable IDs during staging; persist only on explicit save.
- Maintain `core.version` and existing driver/service import facades while internals move.
- Keep old settings locations readable for at least one migration cycle.
- Introduce new services behind adapters so each phase can be reverted independently.

## 10. Verification gates

| Gate | Required evidence |
|---|---|
| Compatibility | Golden old projects and CSV fixtures open/import without manual changes. |
| Correctness | Unit/contract/integration suites pass with deterministic clocks. |
| Responsiveness | No network or bulk parsing on Tk thread; UI latency budget measured. |
| Scale | 100, 1,000, 2,000 and 5,000-tag benchmarks and soak results. |
| Lifecycle | Repeated open/close/connect/disconnect leaves no threads or Tk callbacks. |
| Drivers | Contract suite plus simulator/HIL matrix per supported protocol. |
| Packaging | Source, Linux and Windows artifacts report consistent version and settings paths. |
| Security | Size limits, path validation, plugin policy and external API threat model. |

## 11. Risks of the roadmap

| Risk | Mitigation |
|---|---|
| Event ordering changes current behavior | Characterize current order; add revisions and deterministic queues. |
| Stable-ID migration breaks references | Stage mappings, retain names, golden project round trips. |
| Worker I/O introduces races | Immutable snapshots, single-writer runtime store, bounded queues. |
| Driver abstraction hides vendor capabilities | Capability interfaces instead of lowest-common-denominator API. |
| Refactoring delays features | Thin compatibility adapters and vertical, releasable phases. |
| Plugin/API work expands security surface | Threat model before public SDK or network endpoint. |

## 12. Definition of done

The architectural program is complete when domain engines run without Tk, all PLC I/O is bounded and off the UI thread, runtime changes use stable identities and typed events, supported drivers pass one contract suite, old projects remain compatible, settings/logs use safe user paths, large-list views meet the 5,000-tag performance budget, and Linux/Windows releases are reproducible in CI.
