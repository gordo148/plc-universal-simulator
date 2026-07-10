@echo off
setlocal

set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%" || exit /b 1
if not defined PYTHON set "PYTHON=python"

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

"%PYTHON%" -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo PyInstaller is not installed for %PYTHON%. 1>&2
    echo Install dependencies with: %PYTHON% -m pip install -r requirements.txt 1>&2
    exit /b 1
)

"%PYTHON%" scripts\generate_version.py
if errorlevel 1 exit /b 1

"%PYTHON%" -m PyInstaller --clean --noconfirm plc-universal-simulator.spec
if errorlevel 1 exit /b 1

if not exist "dist\PLC Universal Simulator.exe" (
    echo Build did not create dist\PLC Universal Simulator.exe 1>&2
    exit /b 1
)

echo Build complete: %PROJECT_ROOT%\dist\PLC Universal Simulator.exe
