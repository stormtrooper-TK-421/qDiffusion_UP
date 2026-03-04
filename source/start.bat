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

set "PYTHONNOUSERSITE=1"
set "PYTHONDONTWRITEBYTECODE=1"
set "QML_DISABLE_DISK_CACHE=1"
set "QT_DISABLE_SHADER_DISK_CACHE=1"
set "QSG_RHI_DISABLE_SHADER_DISK_CACHE=1"

".\python\python.exe" scripts\bootstrap.py
if errorlevel 1 (
    echo Bootstrap failed.
    exit /b 1
)

set "VIRTUAL_ENV=%CD%\.venv"
start "" ".\.venv\Scripts\python.exe" source\launch.py
exit /b 0
