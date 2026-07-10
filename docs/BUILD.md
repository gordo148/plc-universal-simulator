# Build and CSV templates

The PyInstaller build must include the complete top-level `templates/` folder.
This is configured in `plc-universal-simulator.spec`; no manual copy step is
required.

Build from the repository root:

```bash
./scripts/build_linux.sh
```

The Linux and Windows build scripts generate `core/version.py` from the current
Git tag before running PyInstaller. The packaged application reads that module
at runtime and does not need Git or the repository metadata.

## Version generation

Release tags must use `vMAJOR.MINOR.PATCH`, optionally followed by `-alphaN`,
`-betaN`, or `-rcN`. Examples include `v2.2.2` and `v2.3.0-rc1`. Other tag
formats are ignored by the version generator.

An exact valid tag produces a release version. Otherwise, the nearest valid tag
reachable from `HEAD` is combined with the commit distance and short hash, such
as `2.2.2+3.gabc1234`. A dirty tree adds `.dirty`. If no valid tag is reachable,
the version starts at `0.0.0`; if Git or repository metadata is unavailable, the
committed values in `core/version.py` are used safely.

`core/version.py` is the only runtime version source. Git is never invoked by
the installed application, and `.git` is not included by PyInstaller. At
runtime, the About dialog reports `Source development build` when launched with
Python and `Packaged desktop build` when frozen by PyInstaller.

The committed module always retains the latest known release version. The build
generator atomically refreshes the version, release type, short commit, branch,
and UTC build date. No release or development workflow ever requires manual
editing of `core/version.py`. The development fallback is used only when Git
metadata genuinely cannot be determined.

## Stable release workflow

Creating a release requires only:

```bash
git add .
git commit -m "Describe the release changes"
git tag -a v2.2.2 -m "Release v2.2.2"
git push origin main
git push origin v2.2.2
./scripts/build_linux.sh
./scripts/install_linux.sh
```

Builds made after the tagged commit include the commit count and hash as
development metadata. Builds from a modified working tree also end in `.dirty`.

On Windows, push the commit and tag in the same way, then run:

```bat
scripts\build_windows.bat
scripts\install_windows.bat
```

## Correcting an incorrect tag

The generator may warn when reachable tags contain multiple major release
lines. Obsolete or incorrect tags are never modified automatically. A
maintainer can remove an incorrect local tag with:

```bash
git tag -d v1.1.1
```

If the tag was pushed, it can be removed remotely with:

```bash
git push origin --delete v1.1.1
```

Deleting a published tag can disrupt other users and release automation. Do it
only intentionally and after confirming that the tag is incorrect.

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
