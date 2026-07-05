@echo off
setlocal

set "PROJECT_ROOT=%~dp0.."
set "BUILD_EXE=%PROJECT_ROOT%\dist\PLC Universal Simulator.exe"
set "INSTALL_DIR=%LOCALAPPDATA%\PLCUniversalSimulator"
set "INSTALL_EXE=%INSTALL_DIR%\PLC Universal Simulator.exe"
set "USER_DATA_DIR=%LOCALAPPDATA%\PLCUniversalSimulatorData"

if not exist "%BUILD_EXE%" (
    call "%PROJECT_ROOT%\scripts\build_windows.bat"
    if errorlevel 1 exit /b 1
)

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if errorlevel 1 exit /b 1

copy /y "%BUILD_EXE%" "%INSTALL_EXE%" >nul
if errorlevel 1 exit /b 1

set "PLCUSIM_INSTALL_DIR=%INSTALL_DIR%"
set "PLCUSIM_USER_DATA_DIR=%USER_DATA_DIR%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ErrorActionPreference = 'Stop';" ^
    "$installRoot = $env:PLCUSIM_INSTALL_DIR;" ^
    "$dataRoot = $env:PLCUSIM_USER_DATA_DIR;" ^
    "foreach ($name in @('config', 'configs', 'logs')) {" ^
    "  $source = Join-Path $dataRoot $name;" ^
    "  if (Test-Path -LiteralPath $source) {" ^
    "    $destination = Join-Path $installRoot $name;" ^
    "    New-Item -ItemType Directory -Path $destination -Force | Out-Null;" ^
    "    Get-ChildItem -LiteralPath $source -Force | Copy-Item -Destination $destination -Recurse -Force;" ^
    "    Remove-Item -LiteralPath $source -Recurse -Force;" ^
    "  }" ^
    "}" ^
    "if (Test-Path -LiteralPath $dataRoot) { Remove-Item -LiteralPath $dataRoot -Force -ErrorAction SilentlyContinue; }" ^
    "$desktop = [Environment]::GetFolderPath('Desktop');" ^
    "$target = Join-Path $env:PLCUSIM_INSTALL_DIR 'PLC Universal Simulator.exe';" ^
    "$shortcutPath = Join-Path $desktop 'PLC Universal Simulator.lnk';" ^
    "$shell = New-Object -ComObject WScript.Shell;" ^
    "$shortcut = $shell.CreateShortcut($shortcutPath);" ^
    "$shortcut.TargetPath = $target;" ^
    "$shortcut.WorkingDirectory = [Environment]::GetFolderPath('MyDocuments');" ^
    "$shortcut.IconLocation = $target + ',0';" ^
    "$shortcut.Save()"
if errorlevel 1 exit /b 1

echo Installed PLC Universal Simulator in %INSTALL_DIR%
