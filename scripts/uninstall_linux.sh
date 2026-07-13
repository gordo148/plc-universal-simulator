#!/usr/bin/env bash
set -euo pipefail

APPLICATION_DIR="${HOME}/.local/share/plc-universal-simulator"
EXECUTABLE="${HOME}/.local/bin/plc-universal-simulator"
ICON_THEME_DIR="${HOME}/.local/share/icons/hicolor"
ICON="${ICON_THEME_DIR}/256x256/apps/plc-universal-simulator.png"
LEGACY_ICON="${HOME}/.local/share/icons/plc-universal-simulator.png"
DESKTOP_ENTRY="${HOME}/.local/share/applications/plc-universal-simulator.desktop"
DESKTOP_DIR="${HOME}/.local/share/applications"

rm -rf -- "${APPLICATION_DIR}"
rm -f -- "${EXECUTABLE}" "${ICON}" "${LEGACY_ICON}" "${DESKTOP_ENTRY}"

if command -v gtk-update-icon-cache >/dev/null 2>&1 && [[ -d "${ICON_THEME_DIR}" ]]; then
    gtk-update-icon-cache --force --ignore-theme-index "${ICON_THEME_DIR}"
fi

if command -v update-desktop-database >/dev/null 2>&1 && [[ -d "${DESKTOP_DIR}" ]]; then
    update-desktop-database "${DESKTOP_DIR}"
fi

echo "Uninstalled PLC Universal Simulator"
