# PLC Universal Simulator — Code Metrics Executive Summary

## Purpose

This document is the executive summary of the complete repository metrics and architecture audit. Detailed evidence is available in:

- `docs/CODE_METRICS_REPORT.md`
- `docs/CODE_METRICS_TABLES.md`
- `docs/ARCHITECTURE_GRAPH.md`
- `docs/REFACTORING_PLAN.md`

The assessment is read-only and based on repository structure, Python AST metrics, import-graph analysis, source inspection, tests, documentation, scripts, and packaging configuration.

## Baseline

| Metric | Value |
|---|---:|
| Tracked repository files | 132 |
| Python files assessed | 88 |
| Python physical LOC | 17,842 |
| Python logical/non-comment LOC | 14,882 |
| Test Python LOC | 5,731 |
| Production/support Python LOC | 12,111 |
| Top-level classes | 60 |
| Module-level functions | 721 |
| Methods | 376 |
| Nested functions | 52 |
| Total function definitions | 1,149 |
| Static test definitions | 295 |
| Import statements | 511 |
| Estimated branch points | 1,916 |
| Loops and comprehensions | 581 |
| `try` blocks | 124 |
| Lambdas | 440 |
| Internal dependency cycles | 1 strongly connected component |

The last verified full test run at the reviewed baseline executed **460 passing pytest cases**. Static source contains 295 `test_*` definitions; parametrization explains much of the difference between definitions and collected cases.

## Overall assessment

**Architecture score: 6.4/10**

**Current technical risk: Medium–High**
**Feedback Engine V2 readiness: Partial**

The project is a tested and capable modular desktop monolith. Its core runtime, project transactions, address validation, Dashboard V2, master-detail tables, callback lifecycle, and packaging are strong. Its principal constraint is the concentration of orchestration and mutable state in `ui/main_window.py`, combined with direct UI-to-UI dependencies and synchronous PLC reads on the Tk thread.

## Main strengths

1. Clear persistent-definition/runtime-value separation in `core/tag_model.py` and `core/tag_runtime.py`.
2. Central PLC boundary in `services/plc_service.py`.
3. Transactional and backward-compatible project loading in `ui/project_config.py`.
4. Atomic project/settings writes.
5. Structured Siemens parser in `drivers/siemens_address.py`.
6. Incremental Dashboard reconciliation in `ui/dashboard_tab.py`.
7. Scalable master-detail Digital, Analog, and Trends views.
8. Central tracking and cancellation of Tk callbacks.
9. Broad headless regression suite.
10. Build metadata generation that leaves tracked source unchanged.

## Main findings

| Finding | Evidence | Priority |
|---|---|---:|
| PLC reads run on the Tk thread | `ui/main_window.py:803–826` | P0 |
| Central application god object | `PLCSimulator`, 1,118 lines, 71 methods | P0 |
| Broad PLC service | `PLCService`, 619 lines, 22 methods | P1 |
| UI dependency cycle | Alarm/Analog/Dashboard/Digital/Project/Tag Manager SCC | P0 |
| No runtime event/subscription layer | Direct calls plus independent timers | P0 |
| Feedback has no domain engine | `ui/feedback_tab.py` is a widget monitor | P0 |
| Alarm BAD quality becomes normal | `ui/alarm_tab.py:236–275` | P0/P1 |
| Feedback and Alarm widgets scale per item | `ui/feedback_tab.py`, `ui/alarm_tab.py` | P1 |
| Tag name is mutable identity | Runtime/features keyed by `tag.name` | P1 |
| New drivers require cross-cutting edits | Service, header, projects, Tag Manager, spec | P1 |
| Requirements are unpinned | `requirements.txt` | P1 |
| No repository CI workflow | No `.github/workflows/` | P1 |

## Complexity hotspots

The AST complexity calculation is a McCabe-style approximation, not a `radon` result.

| Function | Path/line | Complexity | LOC | Max nesting |
|---|---|---:|---:|---:|
| `refresh_dashboard_table` | `ui/dashboard_tab.py:500` | 46 | 65 | 5 |
| `refresh_analog_visible_rows` | `ui/analog_tab.py:245` | 31 | 107 | 2 |
| `read_tags_csv` | `ui/tag_manager.py:984` | 31 | 107 | 5 |
| `suggest_address` | `ui/tag_manager.py:772` | 31 | 73 | 6 |
| `build_project_data` | `ui/project_config.py:139` | 30 | 152 | 4 |
| `_stage_project_data` | `ui/project_config.py:737` | 30 | 103 | 4 |
| `refresh_digital_visible_rows` | `ui/digital_tab.py:262` | 28 | 95 | 2 |
| `_restore_analog_profiles` | `ui/project_config.py:560` | 26 | 67 | 4 |
| `update_dashboard` | `ui/dashboard_tab.py:674` | 26 | 18 | 2 |
| `apply_imported_tags` | `ui/tag_manager.py:1440` | 24 | 122 | 3 |

## Architecture scorecard

| Category | Score |
|---|---:|
| Architecture | 6.4 |
| Organization | 6.0 |
| Scalability | 6.2 |
| Performance | 7.0 |
| Modularity | 5.4 |
| Testability | 7.5 |
| Documentation | 6.8 |
| UX | 7.0 |
| Maintainability | 5.8 |
| Feedback Engine V2 readiness | 5.5 |

## Immediate recommendation

Do not implement Feedback Engine V2 as additional dictionaries, per-feedback callbacks, or widget-owned state in `ui/feedback_tab.py`. First introduce:

1. a pure Feedback definition/runtime/state machine;
2. an injected clock;
3. batched runtime change sets;
4. a small typed event dispatcher;
5. a bounded Treeview/master-detail presentation;
6. persistence adapters that preserve existing projects.

## Priority sequence

```text
Tk-safe polling
    → runtime change sets
        → Feedback domain engine
            → scalable Feedback UI
                → driver contracts / TagRepository
                    → project and CSV extraction
```

## Future-feature readiness

| Feature | Readiness | Main blocker |
|---|---|---|
| Feedback Engine V2 | Partial | No domain engine/event layer |
| Recipes | Partial | Mutable name identity and command abstraction |
| Scenario Engine | Low–Partial | No deterministic clock/event model |
| OPC UA | Partial | Driver registry and richer data types |
| MQTT | Low | No pub/sub application events |
| REST API | Low | Application logic depends on Tk application object |
| Plugin SDK | Low | Loader exists, stable extension ports do not |

## Audit interpretation

- Counts are facts from the reviewed repository state.
- Complexity is an explicitly documented AST approximation.
- Unused symbols and duplication are reported as candidates unless manually confirmed.
- Coverage percentage is not claimed because no coverage instrumentation/configuration is present.
- Recommendations are incremental; no rewrite is proposed.
