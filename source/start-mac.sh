#!/bin/sh

set -eu

PYTHON_VERSION="3.14.3"
STANDALONE_REPOS="astral-sh/python-build-standalone indygreg/python-build-standalone"

resolve_standalone_python_url() {
    arch="$1"
    prefix="cpython-${PYTHON_VERSION}+"
    suffix="-${arch}-apple-darwin-install_only.tar.gz"

    for repo in ${STANDALONE_REPOS}; do
        api_url="https://api.github.com/repos/${repo}/releases?per_page=100"
        url=$(curl -fsSL "$api_url" | grep -Eo 'https://[^"[:space:]]+' | grep "/${prefix}" | grep "${suffix}" | head -n 1 || true)
        if [ -n "$url" ]; then
            printf '%s\n' "$url"
            return 0
        fi
    done

    echo "Failed to resolve standalone Python ${PYTHON_VERSION} for macos/${arch}" >&2
    return 1
}

if [ ! -d "./python" ]
then
    arch="x86_64"
    echo "DOWNLOADING PYTHON ${PYTHON_VERSION}..."
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
