# Trends

## Purpose and architecture

Trends records existing runtime tag values without changing PLC polling or
duplicating the sampling engine. The fixed master-detail layout contains one
searchable/sortable `ttk.Treeview`, one reusable editor, one persistent
Matplotlib chart, and one command toolbar. No checkbox, Tk variable, trace, or
callback is allocated per tag. Page sizes are 25, 50, 100, and 250.

## Search, filters, and sorting

Search matches name, address, and type after a 150 ms debounce. Escape clears
the query and Ctrl+F focuses it. Filters include All, Enabled, Disabled, BOOL,
INT, REAL, Visible, and Hidden. Search and filters work together. Clicking any
heading toggles ascending/descending order, preserving selection when possible.

## Selected-tag editor

The reusable editor controls Trend enabled state, color, line width, axis,
visibility, sample rate, history size, and buffer size. Enable/Disable,
Show/Hide, and Remove affect only the selected tag. With no result, controls
are disabled safely.

Existing `enabled_trend`, selected-curves, and auto-scale project fields remain
compatible. Old projects require no migration. Extra curve presentation values
are runtime UI settings and do not alter project or CSV formats.

## Commands and navigation

Start Trend, Stop Trend, Clear, Export CSV, and Auto Scale use the existing
recorder and plot. Selection never recreates the chart.

| Input | Action |
| --- | --- |
| ↑ / ↓ | Previous or next row |
| PageUp / PageDown | Move by the visible table height |
| Home / End | First or last visible row |
| Enter / Space | Toggle Trend enabled |
| Delete | Disable and remove selected curve |
| Double-click | Toggle Trend enabled |
| Ctrl+F | Focus search |
| Escape | Clear focused search |

Right-click offers Enable Trend, Disable Trend, Show, Hide, Copy Name, and Copy
Address.

## Lifecycle and performance

Trends-owned sample/debounce callbacks and pending Matplotlib idle draws are
cancelled before Tk destruction. Cleanup never walks per-tag widgets. Run
`scripts/benchmark_trends_ui.py` for repeatable 100/1,000/5,000-tag tests
without a PLC.
