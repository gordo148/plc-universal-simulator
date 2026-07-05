# -*- mode: python ; coding: utf-8 -*-

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


project_root = os.path.abspath(SPECPATH)
excluded_data_parts = {
    ".git",
    "__pycache__",
    "docs",
    "screenshots",
    "tests",
}


def optional_submodules(package):
    try:
        return collect_submodules(package)
    except Exception:
        return []


def include_data_file(item):
    source, destination = item
    parts = set(os.path.normpath(source).split(os.sep))
    parts.update(os.path.normpath(destination).split(os.sep))
    return parts.isdisjoint(excluded_data_parts)


# CustomTkinter themes and assets are runtime requirements. No project folders
# are collected as data, which keeps tests, docs, screenshots, .git, and cache
# directories out of the packaged application.
datas = [
    item
    for item in collect_data_files("customtkinter")
    if include_data_file(item)
] + [
    (os.path.join(project_root, "templates"), "templates"),
    (os.path.join(project_root, "assets", "icon.png"), "assets"),
]
hiddenimports = optional_submodules("customtkinter") + [
    "drivers.internal_simulator",
    "drivers.modbus_tcp",
    "drivers.omron_fins",
    "drivers.rockwell_enip",
    "drivers.schneider_modbus",
    "drivers.siemens_s7",
]

a = Analysis(
    [os.path.join(project_root, "main.py")],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={
        "matplotlib": {
            "backends": ["TkAgg"],
        },
    },
    runtime_hooks=[],
    excludes=[
        "pytest",
        "tests",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="plc-universal-simulator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="plc-universal-simulator",
)
