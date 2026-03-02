#!/usr/bin/env python3
"""Shared hermetic environment setup for repository-local entrypoints."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = REPO_ROOT / ".venv"
TMP_ROOT = REPO_ROOT / ".tmp"

STRIP_PREFIXES = ("QT_", "QML_", "PYTHON", "PIP")


def venv_python() -> Path:
    python_bin = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / "python"
    if not python_bin.is_file():
        raise SystemExit(
            "Missing .venv interpreter. Run `PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 "
            "python scripts/bootstrap.py --mode all` first."
        )
    return python_bin


def _strip_inherited_environment() -> dict[str, str]:
    clean_env: dict[str, str] = {}
    for key, value in os.environ.items():
        key_upper = key.upper()
        if key_upper.startswith(STRIP_PREFIXES):
            continue
        clean_env[key] = value
    return clean_env


def _ensure_tmp_layout() -> dict[str, str]:
    xdg_cache = TMP_ROOT / "xdg_cache"
    xdg_config = TMP_ROOT / "xdg_config"
    xdg_data = TMP_ROOT / "xdg_data"
    xdg_state = TMP_ROOT / "xdg_state"

    for path in (TMP_ROOT, xdg_cache, xdg_config, xdg_data, xdg_state):
        path.mkdir(parents=True, exist_ok=True)

    return {
        "TMPDIR": str(TMP_ROOT),
        "TEMP": str(TMP_ROOT),
        "TMP": str(TMP_ROOT),
        "XDG_CACHE_HOME": str(xdg_cache),
        "XDG_CONFIG_HOME": str(xdg_config),
        "XDG_DATA_HOME": str(xdg_data),
        "XDG_STATE_HOME": str(xdg_state),
    }


def build_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = _strip_inherited_environment()
    env.update(_ensure_tmp_layout())
    env.update(
        {
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PIP_NO_CACHE_DIR": "1",
            "QML_DISABLE_DISK_CACHE": "1",
            "QT_DISABLE_SHADER_DISK_CACHE": "1",
            "QSG_RHI_DISABLE_SHADER_DISK_CACHE": "1",
            "VIRTUAL_ENV": str(VENV_DIR),
        }
    )

    path_entries: list[str] = []
    venv_bin = str(venv_python().parent)
    if venv_bin:
        path_entries.append(venv_bin)
    inherited_path = env.get("PATH", "")
    if inherited_path:
        path_entries.append(inherited_path)
    env["PATH"] = os.pathsep.join(path_entries)

    if extra:
        env.update(extra)
    return env


def run_with_venv(args: Iterable[str], extra_env: dict[str, str] | None = None) -> int:
    cmd = [str(venv_python()), *args]
    printable = " ".join(cmd)
    print(f"[entrypoint] $ {printable}")
    completed = subprocess.run(cmd, cwd=str(REPO_ROOT), env=build_env(extra_env), check=False)
    return completed.returncode


def _main_not_supported() -> None:
    raise SystemExit("Use scripts/run_gui.py, scripts/run_tests.py, or scripts/run_infer_server.py")


if __name__ == "__main__":
    _main_not_supported()
