@echo off
setlocal

set "INSTALL_DIR=%LOCALAPPDATA%\PLCUniversalSimulator"
set "USER_DATA_DIR=%LOCALAPPDATA%\PLCUniversalSimulatorData"

set "PLCUSIM_INSTALL_DIR=%INSTALL_DIR%"
set "PLCUSIM_USER_DATA_DIR=%USER_DATA_DIR%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ErrorActionPreference = 'Stop';" ^
    "$shortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'PLC Universal Simulator.lnk';" ^
    "Remove-Item -LiteralPath $shortcut -Force -ErrorAction SilentlyContinue;" ^
    "$installRoot = $env:PLCUSIM_INSTALL_DIR;" ^
    "$dataRoot = $env:PLCUSIM_USER_DATA_DIR;" ^
    "if (Test-Path -LiteralPath $installRoot) {" ^
    "  foreach ($name in @('config', 'configs', 'logs')) {" ^
    "    $source = Join-Path $installRoot $name;" ^
    "    if (Test-Path -LiteralPath $source) {" ^
    "      $destination = Join-Path $dataRoot $name;" ^
    "      New-Item -ItemType Directory -Path $destination -Force | Out-Null;" ^
    "      Get-ChildItem -LiteralPath $source -Force | Copy-Item -Destination $destination -Recurse -Force;" ^
    "    }" ^
    "  }" ^
    "  Remove-Item -LiteralPath $installRoot -Recurse -Force;" ^
    "}"
if errorlevel 1 exit /b 1

echo Uninstalled PLC Universal Simulator
