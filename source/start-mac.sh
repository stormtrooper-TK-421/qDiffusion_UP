#!/bin/sh

if [ ! -d "./python" ]
then
    arch="x86_64"
    if [ "$(uname -m)" = "arm64" ]; then
        arch="aarch64"
    fi
    echo "DOWNLOADING PYTHON 3.14.3 ($arch)..."
    curl -L --progress-bar "https://github.com/astral-sh/python-build-standalone/releases/download/20260203/cpython-3.14.3+20260203-$arch-apple-darwin-install_only.tar.gz" -o "python.tar.gz"
    echo "EXTRACTING PYTHON..."
    tar -xf "python.tar.gz"
    rm "python.tar.gz"
fi

if [ ! -d ".venv" ]; then
    echo "BOOTSTRAPPING VIRTUAL ENVIRONMENT..."
    ./python/bin/python3 scripts/bootstrap.py --mode gui
    if [ $? -ne 0 ]; then
        echo "Failed to bootstrap virtual environment."
        exit 1
    fi
fi

./python/bin/python3 scripts/run_gui.py "$@"
