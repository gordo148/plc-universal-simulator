# Dashboard v2 — Implementation Decisions

## DEC-001 — Deterministic column reordering instead of header drag

- **Requirements considered:** the earlier column request preferred header
  drag-and-drop; SDS UXC/COL/Volume 4 and EXEC-003 explicitly require a reliable
  Move Left/Move Right fallback when ttk header dragging cannot be validated
  cross-platform.
- **Decision:** provide Move Left and Move Right actions in the Columns menu for
  the currently targeted column. Do not advertise native header drag.
- **Reason:** `ttk.Treeview` has no native reorder gesture. Custom bindings
  conflict with separator resizing and heading commands and vary between Linux
  and Windows Tk. Deterministic commands preserve accessibility and correctness.
- **Impact:** all ordering capability and persistence remain available, but the
  gesture differs from Excel. This is a documented SDS-approved fallback.

## DEC-002 — Project-scoped name as Dashboard identity

- **Requirements considered:** CTX-003/DATA-001 prefer stable identity; the
  current model/runtime cache has no persistent tag ID and validates names as
  unique.
- **Decision:** isolate identity as tag name and clear mappings/selection on
  project generation changes. Do not add a project-schema ID migration.
- **Reason:** an ID migration would expand scope and risk old projects, CSV and
  every consumer. Name is already the runtime cache key and existing reference.
- **Impact:** renaming a tag is a structural change; Dashboard remaps it on the
  next safe refresh. The limitation is explicit rather than hidden.

## DEC-003 — Statistics use complete Dashboard-eligible population

- **Requirements considered:** UXH-002 and STAT-001 require one documented rule.
- **Decision:** Total, GOOD, BAD, Simulation, Trend and Alarm cards count all
  brand-compatible tags with `enabled_dashboard`; the Showing label reports the
  filtered visible count.
- **Reason:** operational totals remain stable while search/filtering narrows the
  working list, matching the SDS recommendation.
- **Impact:** filters do not change card totals; they change Showing only.
