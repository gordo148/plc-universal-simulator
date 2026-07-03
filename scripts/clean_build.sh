#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

if [[ ! -f "plc-universal-simulator.spec" || ! -f "main.py" ]]; then
    echo "Refusing to clean outside the PLC Universal Simulator repository." >&2
    exit 1
fi

if [[ -d "build" ]]; then
    find build -mindepth 1 -maxdepth 1 ! -name README.md -exec rm -rf -- {} +
fi
rm -rf -- dist

find . -type d -name __pycache__ -prune -exec rm -rf -- {} +
rm -rf -- .pytest_cache

echo "Generated build artifacts removed."
