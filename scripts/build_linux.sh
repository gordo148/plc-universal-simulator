#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PYTHON="${PYTHON:-python3}"

cd "${PROJECT_ROOT}"

if ! "${PYTHON}" -c "import PyInstaller" >/dev/null 2>&1; then
    echo "PyInstaller is not installed for ${PYTHON}." >&2
    echo "Install dependencies with: ${PYTHON} -m pip install -r requirements.txt" >&2
    exit 1
fi

"${PYTHON}" -m PyInstaller \
    --clean \
    --noconfirm \
    plc-universal-simulator.spec

echo "Build complete: ${PROJECT_ROOT}/dist/plc-universal-simulator/"
