# PLC Universal Simulator Architecture

## Version

Current architecture: **v2.2-extensible**

## Purpose

PLC Universal Simulator is a desktop engineering tool for simulation,
monitoring, and PLC signal testing across multiple industrial platforms. The
architecture keeps protocol concerns behind a service boundary and gives every
application feature a shared tag database and runtime-value cache.

## Core principles

1. The Tag Manager is the single source of truth for tag definitions.
2. Runtime values are volatile and separate from persistent configuration.
3. UI modules do not communicate with PLC drivers directly.
4. PLC reads and writes pass through `PLCService`.
5. Driver-specific addressing is validated before communication.
6. Tests use mocked drivers and require no PLC or display server.
7. Plugin loading is dormant and explicitly opt-in.

## High-level data flow

```text
                         Project / CSV files
                                 |
                                 v
                         +----------------+
                         |  Tag Manager   |
                         | TagDefinition  |
                         +-------+--------+
                                 |
             +-------------------+-------------------+
             |                   |                   |
             v                   v                   v
      Runtime UI modules     PLCService         Project builder
      Digital / Analog       read / write        definitions only
      Feedback / PID              |
      Trends / Alarms             v
      Dashboard             Selected PLC driver
             |                   |
             +---------+---------+
                       v
                 RuntimeTagCache
             value / validity / source
```

## Tag model

`core/tag_model.py` defines `TagDefinition` (`Tag` is its compatibility alias).
A tag contains:

- unique `name`
- `data_type`: `BOOL`, `INT`, or `REAL`
- `direction`: `Input`, `Feedback`, `Output`, or `Internal`
- PLC or simulator `address`
- enable flags for simulation, trends, alarms, and dashboard

Tag definitions contain configuration only. They do not contain live PLC
values.

## Runtime Cache

`core/tag_runtime.py` owns volatile `TagRuntime` values keyed by tag name. Each
entry contains:

- current or last raw value
- validity (`GOOD` when valid, `BAD` when invalid)
- update timestamp
- source (`PLC` or `SIMULATION`)

Invalidation marks quality bad but intentionally preserves the last raw value.
Synchronizing definitions preserves runtime state only while the tag signature
remains compatible. Runtime values are never serialized into project files.

## PLCService boundary

`services/plc_service.py` is the only application boundary for PLC connections,
polling, decoding, and writes. It:

- creates the selected driver
- manages connection and disconnection
- routes reads and writes by brand and data type
- decodes protocol data into Python values
- updates or invalidates Runtime Cache entries
- isolates driver exceptions from UI code

UI modules call PLCService methods and do not import protocol clients.

## Drivers

Drivers live under `drivers/` and expose a small protocol-specific transport
surface.

| Driver | Protocol and mapping |
| --- | --- |
| `siemens_address.py` | Central Siemens absolute-address parser and type validation |
| `siemens_s7.py` | Siemens S7 transport for DB, M, I and Q areas |
| `schneider_modbus.py` | Schneider Modbus TCP coils and holding registers |
| `modbus_tcp.py` | Generic Modbus TCP using the shared Modbus transport |
| `rockwell_enip.py` | Rockwell EtherNet/IP symbolic tags via pycomm3 |
| `omron_fins.py` | Omron FINS/UDP CIO bits and DM numeric memory |
| `internal_simulator.py` | In-process typed memory with no network dependency |

The Internal Simulator is treated as a normal online driver. Its values persist
for the current application session, including simulator reconnects, but are not
project data.

The Omron driver handles a missing `fins-driver` import lazily. Other drivers and
application startup remain available; attempting an Omron connection reports a
clear dependency error.

## UI composition

`ui/main_window.py` creates the application shell and tabs. Feature modules
consume tags and Runtime Cache values:

- `tag_manager.py`: tag CRUD, address validation, suggestions, and CSV workflows
- `digital_tab.py`: boolean input controls
- `analog_tab.py` / `analog_profiles.py`: numeric input controls and profiles
- `feedback_tab.py`: feedback display
- `pid_tab.py` / `pid_logic.py`: PID configuration and runtime loop
- `trend_tab.py`: selected-tag history and export
- `alarm_tab.py`: threshold evaluation and acknowledgement
- `dashboard_tab.py`: enabled-tag overview and events
- `project_config.py`: project staging, validation, atomic persistence, rollback
- `header.py`: brand selection, connection settings, and status

Generated controls reference the same `TagDefinition` instances held by the Tag
Manager. Brand changes regenerate compatible runtime views without creating a
second tag database.

## Operating modes

### Offline simulation

Without a PLC connection, enabled input controls can write simulation-sourced
Runtime Cache values. No driver or network operation occurs.

### Online physical PLC

PLCService polls the selected physical driver and marks values with PLC source.
Failed reads invalidate affected entries while retaining their last values.

### Online Internal Simulator

The Simulator brand hides network settings and connects immediately to
in-process memory. Reads and writes still pass through PLCService, so digital,
analog, feedback, PID, trend, alarm, and dashboard modules use the same online
path as physical PLCs.

## Address management

Address validation and suggestions are brand-aware in `ui/tag_manager.py`:

- Siemens: `%DB14.DBX0.0`, `%DB20.DBW10`, `%MD20`, `%I0.0`, `%QW10`
- Schneider: `%M0`, `%MW10`
- Generic Modbus TCP: `%M0`/`M0`/`0`, `%MW0`/`MW0`/`0`
- Rockwell: symbolic tag name; the UI derives address from tag name
- Omron: `CIO0.00`, `D100`, and two-word REAL starting addresses
- Simulator: any non-empty internal address

CSV import validates every row before replacing the active tag list. Address
suggestions account for occupied bits, words, and multi-word values where the
protocol requires it.

## Persistence

`ui/project_config.py` uses a versioned JSON format with the `.simproject`
extension. Loading follows a staged transaction:

1. Parse JSON.
2. Validate format, version, sections, tags, and names.
3. Stage a normalized copy.
4. Apply configuration to the UI and Tag Manager.
5. Restore the previous project and Runtime Cache snapshot if application fails.

Saving writes to a temporary file, flushes it, and atomically replaces the
destination. Runtime values and internal simulator memory are excluded.

## CSV interchange

Universal CSV files contain tag definitions, an optional human-readable
`Comment`, and feature flags. Vendor importers preserve supported comment
columns while normalizing Siemens TIA Portal and Schneider exports into
`TagDefinition` objects. Comments are persisted and searchable presentation
metadata only; drivers never use them for PLC addressing or communication.
Parsing completes before imported tags are applied, preventing partial imports.

## Plugin readiness

`services/plugin_service.py` is a minimal future-facing loader. It imports only
module names explicitly passed to `PluginService.load()`. Normal application
startup does not instantiate it, scan directories, import plugins, or invoke
registration hooks.

Future plugins must use the Tag Manager and existing services rather than own
tag databases or direct driver access. Discovery, activation, permissions,
configuration, lifecycle, and compatibility APIs are not yet defined.

## Tests

The `tests/` package covers tag validation, address formats, Runtime Cache,
project files, CSV atomicity, PLCService routing, physical-driver wrappers,
Internal Simulator behavior, and the dormant plugin loader. Drivers are mocked;
the suite is headless and does not start the GUI.

## Packaging

`plc-universal-simulator.spec` defines a Linux PyInstaller one-folder build.
`scripts/build_linux.sh` creates `dist/plc-universal-simulator/`, while
`scripts/clean_build.sh` removes generated output. Tests, docs, screenshots,
Git metadata, and cache directories are excluded from the application bundle.
