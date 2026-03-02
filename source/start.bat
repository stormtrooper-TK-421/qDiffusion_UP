@echo off
setlocal

if not exist "python\python.exe" (
    if exist "..\python\python.exe" (
        cd ..
    )
)

if not exist "python\python.exe" (
    echo DOWNLOADING PYTHON 3.14.3...
    bitsadmin.exe /transfer "DOWNLOADING PYTHON 3.14.3" "https://github.com/arenasys/binaries/releases/download/v1/cpython-3.14.3+windows-x86_64-install_only.zip" "%CD%\python.zip"

    if errorlevel 1 (
        echo Failed to download Python runtime.
        exit /b 1
    )

    echo EXTRACTING PYTHON...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force '%CD%\python.zip' '%CD%'"
    if errorlevel 1 (
        echo Failed to extract Python runtime.
        del /q "%CD%\python.zip" 2>nul
        exit /b 1
    )

    del /q "%CD%\python.zip"
)

start "" ".\python\python.exe" source\launch.py
exit /b 0
