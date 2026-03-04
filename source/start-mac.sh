#!/bin/sh

set -eu

if [ ! -d "./python" ]
then
    echo "DOWNLOADING PYTHON..."
    curl -L --progress-bar "https://github.com/indygreg/python-build-standalone/releases/download/20240726/cpython-3.10.14+20240726-x86_64-apple-darwin-install_only.tar.gz" -o "python.tar.gz"
    echo "EXTRACTING PYTHON..."
    tar -xf "python.tar.gz"
    rm "python.tar.gz"
fi

export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
export QML_DISABLE_DISK_CACHE=1
export QT_DISABLE_SHADER_DISK_CACHE=1
export QSG_RHI_DISABLE_SHADER_DISK_CACHE=1

./python/bin/python3 scripts/bootstrap.py
export VIRTUAL_ENV="$(pwd)/.venv"
exec "./.venv/bin/python3" source/launch.py "$@"
