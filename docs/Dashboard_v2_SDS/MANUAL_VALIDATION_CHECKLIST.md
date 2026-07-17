# Dashboard v2 — Manual Validation Checklist

Record pass/fail, platform/Tk version and notes for each item.

| # | Pre-condition | Action | Expected result |
| --- | --- | --- | --- |
| 1 | No project loaded | Run `python main.py`, open Dashboard | No error dialog; explicit no-dashboard-tags state; cards show zero/offline semantics |
| 2 | Empty `.simproject` | Open project | Dashboard remains usable; no stale rows/details |
| 3 | Project with ~50 mixed tags | Open project and Dashboard | Eligible rows appear once; Total/GOOD/BAD/feature cards are credible |
| 4 | Generated/imported 1,000+ tags | Scroll rapidly | UI remains interactive; no per-row widgets or seconds-long freeze |
| 5 | Full View | Open Columns, toggle Address/Comment/Source | Visibility changes immediately; selection, rows and vertical scroll stay stable |
| 6 | Full View | Attempt to hide Name | Name remains visible; no modal error |
| 7 | Full View | Use Reorder → Move Left/Right | Visible order changes deterministically without row recreation |
| 8 | Full View | Drag separators, close and restart | Final widths restore; intermediate pixels are not written repeatedly |
| 9 | Long names/comments | Double-click a heading separator; run Auto Fit Visible | Width fits visible sample and remains within usable cap |
| 10 | Custom Full layout | Enable Compact View | Exactly Status, Name, Value and Comment appear; selection/scroll remain stable |
| 11 | Compact View | Disable it | Exact prior visibility, order and widths return |
| 12 | Compact enabled | Restart app and switch projects | Compact persists across restart/project; project dirty state does not change |
| 13 | Tags with Unicode comments | Search name, address, type and accented comment | Case-insensitive matching works; Showing is visible/total |
| 14 | Mixed valid/invalid tags | Combine GOOD/BAD, feature and type filters | OR within status/types and AND across categories; Clear Filters resets only filters |
| 15 | Filter with no matches | Apply search/filter | Explicit “No tags match…” message appears, not a blank loading-like table |
| 16 | Populated table | Click each sortable heading twice | Name/Address/Type/Value/Status alternate ▲/▼; only active heading has one arrow |
| 17 | Live values, sorted by Value | Observe several cycles | Cells update but rows do not jump continuously; explicit heading click resorts |
| 18 | Selected BOOL and numeric tags | Navigate rows with arrows/Page/Home/End | Focus/selection remain visible; inspector changes immediately without flicker |
| 19 | Selected tag with long comment | Inspect right panel and scroll it | General/Values/Configuration/Diagnostics are readable; empty values show em dash |
| 20 | Selected False/0 tag | Observe Values | False and zero are shown, never treated as unavailable |
| 21 | Selected row | Right-click; copy each field | Clipboard receives plain text silently, including empty comment |
| 22 | Selected row | Locate in Tag Manager / Open in Trends | Existing target tab opens and reveals the same tag; unsupported state fails safely |
| 23 | Narrow and maximised window | Move central splitter | Both panes retain minimum usable widths; splitter restores safely after restart |
| 24 | Offline Siemens project | Open Dashboard, search DB/M/I/Q tags | Addresses/comments display; no driver action or unexpected BAD inference from connection alone |
| 25 | Schneider project | Open Dashboard and exercise filters/details | Schneider tags render through the same generic path; communication behaviour unchanged |
| 26 | Legacy project in `configs/` | Open, use Dashboard, save | Project opens; layout remains user-owned; existing configs/projects migration behaviour remains |
| 27 | Real imported CSV | Verify comments and feature flags | Comments search/display/copy correctly; Dashboard eligibility matches imported flags |
| 28 | Live PLC/PLCSIM | Observe updates, Trends, Alarmes, Feedbacks | Dashboard reflects shared runtime state without changing these engines |
| 29 | Project A selected tag, then Project B with same name | Switch projects | Old selection/details do not leak into Project B |
| 30 | Dashboard updating | Close application immediately | No TclError, widget-after-destroy access or blocked preference write |
