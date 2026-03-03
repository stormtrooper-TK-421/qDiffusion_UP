@echo off
setlocal

if not exist "python\python.exe" (
    if exist "..\python\python.exe" (
        cd ..
    )
)

if not exist "python\python.exe" (
    echo DOWNLOADING PYTHON 3.14.3...
    bitsadmin.exe /transfer "DOWNLOADING PYTHON 3.14.3" "https://www.python.org/ftp/python/3.14.3/python-3.14.3-amd64.zip" "%CD%\python.zip"

    if errorlevel 1 (
        echo Failed to download Python runtime.
        exit /b 1
    )

    echo INSTALLING PYTHON...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "New-Item -ItemType Directory -Force '%CD%\python' | Out-Null; Expand-Archive -Force '%CD%\python.zip' '%CD%\python'"
    if errorlevel 1 (
        echo Failed to install Python runtime.
        del /q "%CD%\python.zip" 2>nul
        exit /b 1
    )

    del /q "%CD%\python.zip"
)

if not exist ".venv" (
    echo BOOTSTRAPPING VIRTUAL ENVIRONMENT...
    ".\python\python.exe" scripts\bootstrap.py --mode gui
    if errorlevel 1 (
        echo Failed to bootstrap virtual environment.
        exit /b 1
    )
)

start "" ".\python\python.exe" scripts\run_gui.py
exit /b 0
