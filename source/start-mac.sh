#!/bin/sh

set -eu

PYTHON_VERSION="3.14.3"
STANDALONE_REPOS="astral-sh/python-build-standalone indygreg/python-build-standalone"

resolve_standalone_python_url() {
    prefix="cpython-${PYTHON_VERSION}+"
    suffix_base="-apple-darwin-install_only.tar.gz"

    for arch in "$@"; do
        suffix="-${arch}${suffix_base}"
        for repo in ${STANDALONE_REPOS}; do
            api_url="https://api.github.com/repos/${repo}/releases?per_page=100"
            url=$(curl -fsSL "$api_url" | grep -Eo 'https://[^"[:space:]]+' | grep "/${prefix}" | grep "${suffix}" | head -n 1 || true)
            if [ -n "$url" ]; then
                printf '%s\n' "$url"
                return 0
            fi
        done
    done

    echo "Failed to resolve standalone Python ${PYTHON_VERSION} for macos arches: $*" >&2
    return 1
}

if [ ! -d "./python" ]
then
    machine_arch="$(uname -m)"
    arch_candidates="x86_64"
    case "$machine_arch" in
        arm64|aarch64)
            arch_candidates="aarch64 arm64"
            ;;
        x86_64)
            arch_candidates="x86_64"
            ;;
    esac
    echo "DOWNLOADING PYTHON ${PYTHON_VERSION} (${machine_arch})..."
    # shellcheck disable=SC2086
    python_url="$(resolve_standalone_python_url ${arch_candidates})"
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
