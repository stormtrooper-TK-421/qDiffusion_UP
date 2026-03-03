@echo off
setlocal

if not exist "python\python.exe" (
    if exist "..\python\python.exe" (
        cd ..
    )
)

if not exist "python\python.exe" (
    echo DOWNLOADING PYTHON 3.14.3...
    bitsadmin.exe /transfer "DOWNLOADING PYTHON 3.14.3" "https://www.python.org/ftp/python/3.14.3/python-3.14.3-amd64.exe" "%CD%\python-installer.exe"

    if errorlevel 1 (
        echo Failed to download Python runtime.
        exit /b 1
    )

    echo INSTALLING PYTHON...
    start /wait "" "%CD%\python-installer.exe" /quiet InstallAllUsers=0 SimpleInstall=1 Include_launcher=0 Include_test=0 Include_doc=0 Include_dev=0 Include_tcltk=0 Include_symbols=0 Include_debug=0 Include_pip=1 Include_venv=1 TargetDir="%CD%\python"
    if errorlevel 1 (
        echo Failed to install Python runtime.
        del /q "%CD%\python-installer.exe" 2>nul
        exit /b 1
    )

    del /q "%CD%\python-installer.exe"
)

start "" ".\python\python.exe" source\launch.py
exit /b 0
