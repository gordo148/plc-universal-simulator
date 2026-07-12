# PLC Universal Simulator

A desktop engineering tool for simulating, monitoring, and testing PLC signals
across multiple industrial protocols.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Version](https://img.shields.io/badge/version-2.2--extensible-green)
![License](https://img.shields.io/badge/license-MIT-orange)

## Project overview

PLC Universal Simulator provides one shared Tag Manager for PLC definitions and
uses that database across digital and analog controls, feedbacks, PID, trends,
alarms, and dashboards. The same project can be used offline, with the built-in
simulator, or with a supported physical PLC.

The application is intended for commissioning preparation, signal testing,
training, and development where a consistent tag model is more useful than a
vendor-specific interface.

## Main features

- Universal Tag Manager with `BOOL`, `INT`, and `REAL` tags
- Input, feedback, output, and internal tag directions
- Digital toggle and pulse controls
- Manual, ramp, random, and step analog profiles
- Runtime value quality and source tracking
- Feedback monitor and dashboard
- Trends and CSV trend export
- High-high, high, low, and low-low alarms
- PID simulation using runtime tags
- Universal CSV import/export
- Bundled universal and PLC-brand CSV templates
- Siemens TIA Portal and Schneider CSV imports
- Atomic `.simproject` save/load
- Online PLC communication and offline signal simulation
- Internal PLC simulator requiring no external hardware
- Headless pytest suite
- Linux one-folder PyInstaller packaging
- Dormant, opt-in plugin loader skeleton for future extensions

## Supported PLC drivers

| Brand | Protocol | Address examples |
| --- | --- | --- |
| Siemens S7 | S7 data blocks | `DBX0.0`, `DBW10`, `DBD20` |
| Schneider Modbus | Modbus TCP | `%M0`, `%MW10` |
| Generic Modbus TCP | Modbus TCP | `%M0`, `M0`, `0`, `%MW10`, `MW10` |
| Rockwell EtherNet/IP | pycomm3 symbolic tags | `Start_Button`, `Tank_Level` |
| Omron FINS | FINS/UDP | `CIO100.05`, `D200`, `D300` |
| Internal Simulator | In-process typed memory | Any non-empty internal address |

Rockwell addresses are derived from tag names in the UI. Omron support uses the
optional `fins-driver` package; the application still starts without it and
shows an installation message if Omron is selected.

## Installation

Python 3.10 or newer with Tk support is required. A virtual environment is
recommended.

```bash
git clone <repository-url>
cd plc-universal-simulator
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Debian/Ubuntu, install Tk if necessary:

```bash
sudo apt install python3-tk
```

## Running from source

From the repository root:

```bash
python main.py
```

No PLC is required to start the application. Select **Simulator** for a fully
internal online connection, or remain offline and use enabled simulation tags.

## Running tests

The tests are headless and use mock drivers; they do not connect to real PLCs.

```bash
python -m pytest -q
```

## Building a Linux release

PyInstaller produces a one-folder build for faster startup:

```bash
./scripts/build_linux.sh
```

The executable is created at:

```text
dist/plc-universal-simulator/plc-universal-simulator
```

Clean generated output with:

```bash
./scripts/clean_build.sh
```

See [build/README.md](build/README.md) for prerequisites, interpreter selection,
package scope, and troubleshooting notes.

## Tag Manager usage

1. Select a PLC brand.
2. Enter a unique tag name.
3. Select `BOOL`, `INT`, or `REAL`.
4. Select the direction: `Input`, `Feedback`, `Output`, or `Internal`.
5. Enter an address or use **Suggest Address**.
6. Enable the required simulation, trend, alarm, and dashboard flags.
7. Add the tag and select **Atualizar Sinais** when required.

Names must be non-empty and unique, case-insensitively. Address validation and
suggestions follow the selected PLC brand. In Rockwell mode the address field
is hidden and the symbolic PLC address is the tag name. Simulator mode accepts
any non-empty internal address.

## Digital and Analog simulation workspace

The simulation tabs use a master-detail layout designed for projects with
thousands of tags. A lightweight, paginated table shows the signal database;
only the selected tag owns a full editor, so changing pages or selecting a row
does not create another set of buttons, entries, or sliders.

- Search filters live after a short debounce and matches name, address, or data
  type. Use the **×** button or **Esc** to clear it.
- Click any column heading to alternate ascending and descending sorting. The
  active heading displays ▲ or ▼.
- Digital rows show live ON/OFF state, PLC and simulated values, and whether
  the values differ. The editor provides Toggle/Pulse mode, pulse duration,
  immediate toggle, and write controls.
- Analog rows show current value, profile, and PLC/simulation difference. The
  selected-tag editor provides exact-value entry, slider, limits, step,
  interval, simulation mode, and profile Start/Stop controls.
- Changed runtime values briefly highlight their table row.
- Right-click a row for force/set and copy commands. Double-click toggles a
  Digital signal or focuses the Analog exact-value editor.

Keyboard shortcuts in either table:

| Key | Action |
| --- | --- |
| ↑ / ↓ | Select previous or next row |
| PageUp / PageDown | Move by the visible table height |
| Home / End | Select first or last visible row |
| Enter / Space | Toggle Digital or edit Analog |
| Delete | Force Digital OFF or set Analog to zero |

Search text, page size, sort order, selected row, and selected tab are stored as
optional UI state in project files. Older project files remain compatible.

## Industrial Dashboard

The Dashboard provides a fixed-layout engineering overview without creating a
widget set per tag. Compact cards summarize PLC and communication health,
project identity, tag-feature counts, simulation, alarms, trends, last read,
and read-cycle duration.

Dashboard-enabled tags appear in a searchable, sortable native table with
quality, source, alarm, and trend state. Quick filters select data types, active
alarms, simulated tags, or PLC-sourced values. Selecting a row updates one
reusable detail panel; double-clicking opens the corresponding Digital or
Analog editor with the same tag selected.

The lower panels expose passive communication diagnostics, the existing alarm
and Trend state, active simulation timers, project status, navigation, Trend
start/stop, simulation stop, and project save actions. Recent meaningful events
are kept in a bounded in-memory list. See [Dashboard documentation](docs/DASHBOARD.md).

The Tag Manager is the source of truth. Deleting or changing a tag affects all
runtime consumers generated from that tag database.

## CSV import and export

Universal tag CSV files use a header row with these exact fields:

```text
name,data_type,direction,address,enabled_sim,enabled_trend,enabled_alarm,enabled_dashboard
```

Example:

```csv
name,data_type,direction,address,enabled_sim,enabled_trend,enabled_alarm,enabled_dashboard
Start_Button,BOOL,Input,DBX0.0,1,true,0,yes
Tank_Level,REAL,Feedback,DBD20,0,1,true,1
```

Rules:

- `data_type`: `BOOL`, `INT`, or `REAL`
- `direction`: `Input`, `Feedback`, `Output`, or `Internal`
- Boolean fields accept `1/0`, `true/false`, or `yes/no`
- Addresses are validated against the currently selected brand
- Invalid rows reject the whole import; tags are not partially replaced
- UTF-8 and UTF-8 with BOM are supported

Dedicated import commands are also available for Siemens TIA Portal and
Schneider exports. Universal CSV export writes the current tag database.

To create a new tag list, select the target PLC brand and choose **Exportar
Template CSV**. Select a destination, edit the copied CSV with your tag names
and addresses, then import it with **Import CSV**. Siemens, Schneider,
Rockwell, Omron, and Modbus TCP use brand-specific example addresses;
Simulator exports the universal template. Existing destination files are only
replaced after confirmation.

## Project files

Projects use the `.simproject` extension and JSON-based application format.
They store:

- PLC brand, IP address, and protocol connection settings
- Tag definitions and feature flags
- Digital and analog configuration
- PID, alarm, trend, dashboard, and analog-profile settings

Project writes are atomic. Files are validated before application, and corrupt
or unsupported projects are rejected. Temporary Runtime Cache values are not
saved, including Internal Simulator memory.

## Offline and online modes

### Offline

The application can edit projects and simulate enabled input tags without a PLC
connection. Offline values are marked as simulation values in the Runtime
Cache. No network request is made.

### Online

Selecting a physical PLC driver and connecting routes reads and writes through
`PLCService` to that driver. Communication failures mark affected runtime values
bad while preserving their last raw value for diagnostics.

### Internal Simulator

Selecting **Simulator** hides network settings. Connect switches the application
to `ONLINE SIM`; all tag reads and writes still pass through `PLCService`, backed
by in-process typed memory. Values persist for the application session but are
not written to project files.

## Screenshots

> Screenshots are placeholders for the current release package.

- Dashboard — screenshot placeholder
- Tag Manager — screenshot placeholder
- Digital and analog simulation — screenshot placeholder
- Trends and alarms — screenshot placeholder
- PLC connection modes — screenshot placeholder

## Architecture and extensibility

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for module boundaries and data
flows. The plugin service is a future-facing skeleton only: plugins are not
discovered, imported, or activated during normal startup. See
[plugins/README.md](plugins/README.md).

## Roadmap

- Define a stable plugin lifecycle and permissions model
- Add explicit plugin configuration and opt-in discovery
- Expand release packaging to Windows and macOS
- Improve protocol diagnostics and connection health reporting
- Add richer project migration tooling
- Evaluate OPC UA and MQTT integrations
- Add release screenshots and end-user tutorials

## License

MIT License. See [LICENSE](LICENSE).
