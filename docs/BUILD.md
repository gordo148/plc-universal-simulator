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
