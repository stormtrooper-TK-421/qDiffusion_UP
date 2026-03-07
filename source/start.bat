@echo off
for /f "tokens=4-7 delims=[.] " %%i in ('ver') do (if %%i==Version (set v=%%j.%%k) else (set v=%%i.%%j))

IF NOT EXIST "python" (
    cd ..
)

IF NOT EXIST "python" (
    echo DOWNLOADING PYTHON...

    IF "%v%" == "10.0" (
        bitsadmin.exe /transfer "DOWNLOADING PYTHON 3.10..." "https://github.com/astral-sh/python-build-standalone/releases/download/20260303/cpython-3.10.20+20260303-x86_64-pc-windows-msvc-shared-install_only.tar.gz" "%CD%/python.tar.gz"
    ) else (
        bitsadmin.exe /transfer "DOWNLOADING PYTHON 3.10..." "https://github.com/astral-sh/python-build-standalone/releases/download/20260303/cpython-3.10.20+20260303-x86_64-pc-windows-msvc-shared-install_only.tar.gz" "%CD%/python.tar.gz"
    )

    echo EXTRACTING PYTHON...
    tar -xf "python.tar.gz"
    del /Q "python.tar.gz"
)

start .\python\python.exe source\launch.py
exit