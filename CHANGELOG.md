# Changelog

This project uses milestone labels for the v2 release line.

## v2.2-extensible

### Added

- Internal PLC Simulator driver with volatile `BOOL`, `INT`, and `REAL` memory
- Simulator online mode with no network configuration
- Opt-in plugin package and minimal loader skeleton
- Linux one-folder PyInstaller specification and build scripts
- Packaging and extensibility documentation
- Automated tests for the simulator, plugin loader, and packaging foundations

### Changed

- Updated project metadata and documentation for all implemented PLC drivers
- Preserved Internal Simulator values for the application session
- Kept runtime values outside `.simproject` persistence
- Made the Omron FINS dependency optional at application startup

## v2.1-industrial-drivers

### Added

- Generic Modbus TCP driver with coils and holding-register support
- Rockwell EtherNet/IP symbolic-tag driver using pycomm3
- Omron FINS/UDP driver for CIO bits and DM words
- Brand-specific connection controls, validation, and address suggestions
- Project persistence for industrial-driver connection settings
- Mocked read/write routing tests requiring no PLC hardware

### Supported addressing

- Siemens: `DBX`, `DBW`, and `DBD`
- Schneider: `%M` and `%MW`
- Generic Modbus TCP: prefixed or numeric coil/register addresses
- Rockwell: symbolic tag names
- Omron: CIO bits and DM words/double words

## v2.0-beta

### Added

- Universal Tag Manager as the shared tag database
- Central Runtime Cache with value validity, timestamps, and source tracking
- PLCService boundary for driver communication
- Siemens S7 and Schneider Modbus drivers
- Digital and analog simulation controls
- Feedback monitor, dashboard, trends, alarms, and PID
- Universal, Siemens TIA, and Schneider CSV import workflows
- Universal CSV export
- Atomic `.simproject` save/load with validation and rollback
- Headless pytest framework

### Architecture

- Separated persistent tag definitions from volatile runtime values
- Routed runtime consumers through the shared Tag Manager and Runtime Cache
- Kept PLC drivers independent from UI modules
