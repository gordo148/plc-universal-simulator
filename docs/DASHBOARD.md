# Dashboard v2

## Architecture

Dashboard v2 remains a lightweight `ttk.Treeview` view over the shared
`TagDefinition` and `RuntimeTagCache` sources. `core/dashboard_model.py` owns
the authoritative column registry, versioned preference validation, pure
search/filter/sort transformations, statistics and bounded auto-fit sizing.
`ui/dashboard_tab.py` owns Tk widgets, event bindings, row reconciliation,
details, context actions and navigation adapters.

Tag names remain the existing project-scoped identity because the current tag
model has no persistent ID. Project application clears identity-to-item
mappings before population, preventing a same-name selection from leaking
between projects.

## User workspace

The central table/Selected Tag split is adjustable. Full View columns are
managed with the Columns menu through validated `displaycolumns`; hiding or
reordering a column never deletes Treeview rows. Name cannot be hidden.
Deterministic Move Left/Right commands are used because custom ttk header drag
is not reliable across Linux and Windows Tk. Manual separator resizing,
double-click Auto Fit and Auto Fit Visible Columns persist bounded widths.

Compact View displays Status, Name, Value and Comment and restores the exact previous
Full View layout. Column layout, widths, compact mode, splitter, filters and
sorting live in the versioned `dashboard_ui` user settings section and never in
`.simproject` files.

## Search, filters and sorting

Search is case-insensitive across name, address, comment and type, including
Unicode comments. Status filters are OR within GOOD/BAD. Feature filters
(Simulation, Trend, Alarm) combine with AND semantics. Selected data types are
OR; all categories and search combine with AND semantics.

Name, Address, Type, Value and Status are sortable. The active heading displays
▲/▼. Numeric values sort numerically and unavailable values remain last.
Value-sorted order remains stable during live cycles to avoid row jumping; it
is recomputed on an explicit sort or structural view change.

## Statistics and details

Cards show Total, GOOD, BAD, Simulation, Trend and Alarm counts over the full
brand-compatible, dashboard-enabled population. The Showing label reports the
filtered visible/total count. Connection state remains explicit text.

Selected Tag is grouped into General, Values, Configuration and Diagnostics.
Static fields are configured only when the selected definition changes;
effective/PLC/simulated values, source, quality and timestamp use a separate
snapshot so unchanged labels are not rewritten. The inspector is vertically
scrollable.

## Incremental rendering and lifecycle

The tracked 750 ms scheduler runs only on the Tk thread. Structural changes
reuse stable item IDs where possible. Routine updates compare per-row display
snapshots and call `Treeview.set()` only for changed cells. They do not delete
and recreate the table, reset selection or modify scroll position. Auto-fit
samples at most 500 visible rows and creates no per-tag widgets.

Shutdown cancels tracked Dashboard callbacks; pending debounced preferences are
already present in memory and the normal atomic settings save flushes them.

## Navigation

The lightweight row tooltip exposes name/address/comment. The context menu can
copy name, address, comment or displayed value and navigate to Tag Manager or
Trends through their existing lazy tab/search/selection workflows. Existing
double-click Digital/Analog navigation is preserved.
