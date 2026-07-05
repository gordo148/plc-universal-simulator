# Build and CSV templates

The PyInstaller build must include the complete top-level `templates/` folder.
This is configured in `plc-universal-simulator.spec`; no manual copy step is
required.

Build from the repository root:

```bash
./scripts/build_linux.sh
```

In the one-folder release, PyInstaller stores these CSV files as application
data. The Tag Manager resolves that bundled location at runtime, including when
the executable is launched from a different working directory.

## Linux desktop installation

From the repository root, run:

```bash
./scripts/install_linux.sh
```

The installer builds the application when `dist/plc-universal-simulator/` is
not present, then installs it for the current user. No root privileges are
required. The application files are installed under
`~/.local/share/plc-universal-simulator/`, with a launcher in `~/.local/bin/`,
an icon in `~/.local/share/icons/`, and a desktop entry in
`~/.local/share/applications/`.

After installation, open the desktop application menu and search for
`PLC Universal Simulator`.

## Linux uninstall

From the repository root, run:

```bash
./scripts/uninstall_linux.sh
```

Uninstalling removes only the installed application, executable launcher,
desktop entry, and icon. User projects, settings, and logs are preserved.

## Windows build

Install the dependencies, including PyInstaller, then run from a Command Prompt:

```bat
scripts\build_windows.bat
```

The script cleans previous build output and creates:

```text
dist\PLC Universal Simulator.exe
```

The Windows executable embeds `assets\icon.ico`. The application continues to
use the bundled PNG icon for its Tk windows.

## Windows desktop installation

Run from a Command Prompt without administrator privileges:

```bat
scripts\install_windows.bat
```

The helper builds the executable when needed, installs it under
`%LOCALAPPDATA%\PLCUniversalSimulator`, and creates
`PLC Universal Simulator.lnk` on the current user's Desktop.

## Windows uninstall

Run:

```bat
scripts\uninstall_windows.bat
```

The helper removes the installed application directory and Desktop shortcut.
Before removal it preserves any `config`, `configs`, and `logs` directories in
`%LOCALAPPDATA%\PLCUniversalSimulatorData`; a later installation restores that
data automatically.
