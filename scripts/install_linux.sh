#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
BUILD_DIR="${PROJECT_ROOT}/dist/plc-universal-simulator"
APPLICATION_DIR="${HOME}/.local/share/plc-universal-simulator"
BIN_DIR="${HOME}/.local/bin"
ICON_DIR="${HOME}/.local/share/icons"
DESKTOP_DIR="${HOME}/.local/share/applications"

if [[ ! -x "${BUILD_DIR}/plc-universal-simulator" ]]; then
    "${PROJECT_ROOT}/scripts/build_linux.sh"
fi

install -d "${APPLICATION_DIR}" "${BIN_DIR}" "${ICON_DIR}" "${DESKTOP_DIR}"
find "${APPLICATION_DIR}" -mindepth 1 -delete
cp -a "${BUILD_DIR}/." "${APPLICATION_DIR}/"
ln -sfn \
    "${APPLICATION_DIR}/plc-universal-simulator" \
    "${BIN_DIR}/plc-universal-simulator"
install -m 0644 \
    "${PROJECT_ROOT}/assets/icon.png" \
    "${ICON_DIR}/plc-universal-simulator.png"
install -m 0644 \
    "${PROJECT_ROOT}/packaging/linux/plc-universal-simulator.desktop" \
    "${DESKTOP_DIR}/plc-universal-simulator.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${DESKTOP_DIR}"
fi

echo "Installed PLC Universal Simulator in ${APPLICATION_DIR}"
