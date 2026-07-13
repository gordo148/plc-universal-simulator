# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [2.2.4] - 2026-07-13

### Added

- Added master-detail Digital and Analog tabs with paginated tag tables and reusable editors.
- Added a master-detail Trends workspace with search, filters, sorting, reusable editing controls, and a persistent chart.
- Added a redesigned Dashboard with runtime summaries, communication diagnostics, searchable tags, selected-tag details, and recent events.
- Added debounced live search to Tag Manager.
- Added repeatable UI stress, Trends benchmark, shutdown profiling, and shutdown integration tools.

### Changed

- Decoupled persistent PLC connection state from Tk widgets so projects and connection settings survive UI rebuilds.
- Changed Siemens DB polling to validated, compact, size-limited read ranges instead of reading one span through the highest address.
- Moved PLC connection attempts off the Tk event thread.
- Added automatic source and packaged-build version metadata generation.

### Fixed

- Fixed shutdown hangs caused by blocked PLC connections, pending UI callbacks, and tag-count-proportional Trends teardown.
- Fixed stale or destroyed connection widgets during PLC brand switching and application shutdown.
- Fixed Siemens DB address validation and failure isolation so affected ranges are invalidated without discarding successful ranges.
- Fixed project serialization and Dashboard connection handling after repeated PLC brand changes.

### Performance

- Replaced per-tag Digital, Analog, and Trends controls with fixed-size master-detail interfaces that scale to thousands of tags.
- Bounded table insertion and refresh work with pagination, filtering, and reusable editors.
- Avoided rebuilding unchanged Dashboard structures during polling.

### Linux

- Added a canonical application identity and matching `WM_CLASS`/`StartupWMClass` for correct GNOME dock grouping and icons.
- Improved build metadata generation, PyInstaller module collection, icon-theme installation, cache refresh, and uninstall cleanup.

### Testing

- Expanded automated coverage for master-detail tabs, pagination, Dashboard, Trends, Tag Manager search, persistent connection state, Linux packaging, version generation, and shutdown behavior.
- Added source and packaged shutdown integration scenarios plus large-project UI benchmarks.
