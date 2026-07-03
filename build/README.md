# Linux Packaging — v2.2

PLC Universal Simulator is packaged with PyInstaller as a one-folder desktop
application. One-folder mode keeps startup fast and places the executable and
its private dependencies under:

```text
dist/plc-universal-simulator/
```

## Prerequisites

- Linux with Python 3 and Tk support
- A clean virtual environment is recommended
- Project dependencies installed from `requirements.txt`

On Debian/Ubuntu, Tk can be installed with `sudo apt install python3-tk` when it
is not already available.

## Build

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./scripts/build_linux.sh
```

Run the packaged application with:

```bash
./dist/plc-universal-simulator/plc-universal-simulator
```

Set `PYTHON` to choose a specific interpreter:

```bash
PYTHON=.venv/bin/python ./scripts/build_linux.sh
```

## Clean

```bash
./scripts/clean_build.sh
```

The clean script removes generated PyInstaller output and Python caches while
preserving this documentation file.

## Package scope

The specification includes application modules and runtime assets required by
CustomTkinter. It does not bundle repository-only content such as tests,
documentation, screenshots, Git metadata, or Python cache directories.

Optional protocol dependencies follow their existing runtime behavior. For
example, the application still starts when the optional Omron FINS dependency
is unavailable and reports the missing package only if Omron is selected.

The build does not change application startup or runtime architecture. Driver
selection, project files, and the dormant plugin loader behave the same as when
running from source.
