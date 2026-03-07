#!/bin/sh

if [ ! -d "./python" ] 
then
    echo "DOWNLOADING PYTHON..."
    curl -L --progress-bar "https://github.com/astral-sh/python-build-standalone/releases/download/20260303/cpython-3.10.20+20260303-x86_64-apple-darwin-install_only.tar.gz" -o "python.tar.gz"
    echo "EXTRACTING PYTHON..."
    tar -xf "python.tar.gz"
    rm "python.tar.gz"
fi
./python/bin/python3 source/launch.py "$@"