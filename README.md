# PLC Universal Simulator

A universal industrial PLC signal simulator for automation engineers.

![Python](https://img.shields.io/badge/Python-3.14-blue)
![Version](https://img.shields.io/badge/version-2.0-green)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## Overview

PLC Universal Simulator is an engineering tool designed to simulate PLC signals from multiple manufacturers through a single application.

Current supported manufacturers:

- Siemens S7
- Schneider Modicon

Planned support:

- Rockwell
- Omron
- Beckhoff
- Mitsubishi

---

## Features

### Signal Simulation

- Digital Inputs
- Analog Inputs
- Pulse Mode
- Toggle Mode
- Analog Profiles

### Monitoring

- Feedback Monitor
- Dashboard
- Trends
- Alarm System

### Control

- PID Simulation

### Project

- Tag Manager
- Save / Load Projects

---

## Roadmap

### Version 2.x

- Universal Tag Manager
- CSV Import
- Siemens TIA Portal Import
- Schneider Control Expert Import
- Feedback Monitor
- Project Templates

### Version 3.x

- OPC UA
- MQTT
- Rockwell Driver
- Omron Driver
- Beckhoff Driver

---

## Technologies

- Python
- CustomTkinter
- Snap7
- PyModbus
- Matplotlib

---

## Linux Build

Install the project dependencies and run the one-folder PyInstaller build:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./scripts/build_linux.sh
```

The packaged application is created at:

```text
dist/plc-universal-simulator/plc-universal-simulator
```

Remove generated build output with:

```bash
./scripts/clean_build.sh
```

See [build/README.md](build/README.md) for packaging details and prerequisites.

---

## License

MIT License
