# PLC Universal Simulator v2.2.4

## Highlights

v2.2.4 is the recommended stable release. It delivers scalable master-detail simulation and Trends interfaces, a redesigned Dashboard, stronger connection lifecycle handling, and improved Linux desktop integration.

The existing v2.2.3 tag contains stale development metadata. It remains available for historical integrity but is obsolete and should not be used for distribution.

## New Features

- Master-detail Digital and Analog tabs use paginated tag tables and reusable editors.
- Trends provides a searchable, sortable, filterable master-detail workspace with a persistent chart.
- Dashboard provides runtime summaries, communication diagnostics, tag details, recent events, and navigation to related tools.
- Tag Manager includes debounced live search.

## Improvements

- PLC connection state is independent of transient UI widgets and survives brand changes and UI rebuilds.
- PLC connection attempts run asynchronously so the Tk event loop remains responsive.
- Siemens polling uses validated, bounded DB ranges and isolates failed ranges.
- Source and packaged builds use generated version metadata.

## Performance

- Digital, Analog, and Trends no longer allocate controls for every tag.
- Pagination, reusable editors, bounded table insertion, and fixed Dashboard structures improve responsiveness for projects containing thousands of tags.
- Trends uses a persistent Matplotlib chart and fixed widget structure to reduce creation and shutdown cost.

## Stability and Bug Fixes

- Fixed shutdown hangs involving blocked connection attempts, pending callbacks, and Trends teardown.
- Fixed stale and destroyed connection-widget references during PLC brand switching.
- Fixed project serialization and Dashboard connection handling after connection UI rebuilds.
- Improved Siemens DB address validation, error reporting, and range-specific cache invalidation.

## Linux

- Corrected GNOME dock icon grouping with consistent application identity, `WM_CLASS`, and `StartupWMClass` values.
- Improved PyInstaller metadata inclusion and build-time version generation.
- Improved installer and uninstaller handling for themed icons, desktop metadata caches, and legacy icon cleanup.

Linux users should rebuild and reinstall the package to receive the updated application identity and packaging changes.

## Testing

- Expanded automated coverage across the new master-detail interfaces, Dashboard, Trends, Tag Manager search, connection lifecycle, Linux packaging, version generation, and shutdown paths.
- Added stress, benchmark, profiling, and source/packaged shutdown integration utilities.

## Upgrade Notes

- Project (`.simproject`) and CSV formats remain compatible; no migration is required.
- v2.2.4 is the recommended stable release for source and packaged distributions.
- Do not distribute from the obsolete v2.2.3 tag because its embedded release metadata is stale.
- Linux users should rebuild with `./scripts/build_linux.sh` and reinstall with `./scripts/install_linux.sh`.
