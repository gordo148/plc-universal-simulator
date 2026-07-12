# Industrial Dashboard

## Purpose and architecture

The Dashboard is an engineering overview of project, PLC, simulation, alarm,
trend, and communication state. Its layout is fixed: 90 CustomTkinter widgets,
one native tag `Treeview`, one native event `Treeview`, and one reusable tag
detail panel. Widget count does not change with the number of tags.

The Dashboard refreshes every 750 ms through the application's tracked callback
scheduler. Summary labels are updated in place. The dashboard tag Treeview is
only repopulated when its filtered/sorted data signature changes; polling does
not rebuild the Dashboard structure or call `generate_signals()`.

## Summary cards and diagnostics

Cards show connection status, PLC brand and endpoint, project, tag-feature
counts, communication health, last successful read, and latest read duration.
Colors distinguish online/healthy, offline/error, warning, and inactive states.

`PLCService` exposes passive operation-level diagnostics: successful/failed
reads and writes, reconnect count, timestamps, and average/latest durations.
Metrics wrap existing calls and do not change driver interfaces or protocol
behavior. Metrics are never emitted once per tag.

## Dashboard tag list

Only `enabled_dashboard` tags appear. The table shows quality, identity,
address, type, value, runtime source, alarm state, and trend state. Search is
debounced and matches name, address, type, and source. Quick filters cover data
types, active alarms, simulation, and PLC source. Every column is sortable.

Double-clicking a row opens Digital for `BOOL`, or Analog for `INT`/`REAL`, and
preserves that tag selection. The reusable detail panel shows PLC, simulated,
and effective values, runtime quality/source, features, and update time.

## Events and integrations

The event table is backed by a bounded 50-entry `deque` and renders the latest
20 meaningful events. Poll cycles are intentionally excluded.

Compact panels summarize alarms, existing Trend recording and buffers,
simulation pulses/profiles, Internal Simulator state, and project metadata.
Buttons navigate to their source tabs, control the existing Trend engine, stop
simulation timers, save projects, and open the project folder. No alarm or
trend engine is duplicated.

## Empty states and performance

Disconnected/no-project/no-tag states use explicit text instead of blank
panels. With 5,000 total tags and 1,000 dashboard tags on the documented Xvfb
test host:

- initial Dashboard creation: 345.344 ms
- unchanged summary refresh: 11.338 ms
- narrow tag search: 6.033 ms
- fixed CTk count: 90 (29 frames, 44 labels, 15 buttons, one entry, one menu)

These measurements exclude desktop compositor variance.
