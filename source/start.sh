#!/bin/bash

set -euo pipefail

SCRIPT=$(realpath "$0")
SCRIPT_DIR=$(realpath "$(dirname "$0")")

cd "$SCRIPT_DIR"

echo "[Desktop Entry]
Exec=$SCRIPT %u
Name=qDiffusion
Icon=$SCRIPT_DIR/launcher/icon.png
MimeType=application/x-qdiffusion;x-scheme-handler/qdiffusion;
Type=Application
StartupNotify=false
Terminal=false" > qDiffusion-handler.desktop
if command -v xdg-desktop-menu >/dev/null 2>&1; then
    xdg-desktop-menu install qDiffusion-handler.desktop || true
fi
if command -v xdg-mime >/dev/null 2>&1; then
    xdg-mime default qDiffusion-handler.desktop x-scheme-handler/qdiffusion || true
fi
rm qDiffusion-handler.desktop
chmod +x "$SCRIPT"

cd ..

PYTHON_VERSION="3.14.3"
STANDALONE_REPOS="astral-sh/python-build-standalone indygreg/python-build-standalone"

resolve_standalone_python_url() {
    local arch="$1"
    local prefix="cpython-${PYTHON_VERSION}+"
    local suffix="-${arch}-unknown-linux-gnu-install_only.tar.gz"

    for repo in ${STANDALONE_REPOS}; do
        local api_url="https://api.github.com/repos/${repo}/releases?per_page=100"
        local url
        url=$(curl -fsSL "$api_url" | grep -Eo 'https://[^"[:space:]]+' | grep "/${prefix}" | grep "${suffix}" | head -n 1 || true)
        if [ -n "$url" ]; then
            printf '%s\n' "$url"
            return 0
        fi
    done

    echo "Failed to resolve standalone Python ${PYTHON_VERSION} for linux/${arch}" >&2
    return 1
}

if [ ! -d "./python" ]
then
    flags=$(grep flags /proc/cpuinfo)
    arch="x86_64"
    if [[ $flags == *"sse4"* ]]; then
        arch="x86_64_v2"
    fi
    if [[ $flags == *"avx2"* ]]; then
        arch="x86_64_v3"
    fi
    if [[ $flags == *"avx512"* ]]; then
        arch="x86_64_v4"
    fi
    echo "DOWNLOADING PYTHON ${PYTHON_VERSION} ($arch)..."
    python_url="$(resolve_standalone_python_url "$arch")"
    curl -L --progress-bar "$python_url" -o "python.tar.gz"

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
