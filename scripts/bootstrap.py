#!/usr/bin/env python3
"""Bootstrap a single hermetic project virtual environment for GUI startup readiness."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = REPO_ROOT / ".venv"
TMP_ROOT = REPO_ROOT / ".tmp"
ML_CACHE_ROOT = TMP_ROOT / "ml_cache"
GUI_REQUIREMENTS = REPO_ROOT / "requirements" / "gui.txt"
PYPI_INDEX_URL = "https://pypi.org/simple"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create/update the repository's single hermetic .venv for startup/GUI readiness only",
        epilog="This bootstrap installs requirements/gui.txt only. Inference/model dependencies are installed later by the installer.",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and recreate .venv before installing startup/GUI requirements",
    )
    return parser.parse_args()


def ensure_supported_python() -> None:
    if sys.version_info < (3, 14, 3):
        version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        raise SystemExit(f"Python 3.14.3+ is required. Current interpreter: {version}")


def _require_file(path: Path, description: str) -> None:
    if not path.is_file():
        raise SystemExit(f"Missing {description}: {path}")


def create_or_recreate_venv(recreate: bool, env: dict[str, str]) -> None:
    if recreate and VENV_DIR.exists():
        shutil.rmtree(VENV_DIR)
    if not VENV_DIR.exists():
        run([sys.executable, "-m", "venv", str(VENV_DIR)], env=env)


def run(cmd: list[str], env: dict[str, str]) -> None:
    printable = " ".join(cmd)
    print(f"[bootstrap] $ {printable}")
    subprocess.run(cmd, check=True, cwd=str(REPO_ROOT), env=env)


def build_hermetic_env() -> dict[str, str]:
    clean_env = {}
    for key, value in os.environ.items():
        key_upper = key.upper()
        if (
            key_upper.startswith("PYTHON")
            or key_upper.startswith("PIP")
            or key_upper.startswith("QT")
            or key_upper.startswith("QML")
        ):
            continue
        clean_env[key] = value

    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    ML_CACHE_ROOT.mkdir(parents=True, exist_ok=True)

    clean_env.update(
        {
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PIP_NO_CACHE_DIR": "1",
            "PIP_CONFIG_FILE": os.devnull,
            "QML_DISABLE_DISK_CACHE": "1",
            "QT_DISABLE_SHADER_DISK_CACHE": "1",
            "QSG_RHI_DISABLE_SHADER_DISK_CACHE": "1",
            "TMPDIR": str(TMP_ROOT),
            "TEMP": str(TMP_ROOT),
            "TMP": str(TMP_ROOT),
            "XDG_CACHE_HOME": str(TMP_ROOT / "xdg_cache"),
            "XDG_CONFIG_HOME": str(TMP_ROOT / "xdg_config"),
            "XDG_DATA_HOME": str(TMP_ROOT / "xdg_data"),
            "XDG_STATE_HOME": str(TMP_ROOT / "xdg_state"),
            "HF_HOME": str(ML_CACHE_ROOT / "hf_home"),
            "TORCH_HOME": str(ML_CACHE_ROOT / "torch_home"),
            "TRANSFORMERS_CACHE": str(ML_CACHE_ROOT / "transformers_cache"),
            "DIFFUSERS_CACHE": str(ML_CACHE_ROOT / "diffusers_cache"),
        }
    )

    for key in (
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "HF_HOME",
        "TORCH_HOME",
        "TRANSFORMERS_CACHE",
        "DIFFUSERS_CACHE",
    ):
        Path(clean_env[key]).mkdir(parents=True, exist_ok=True)

    return clean_env


def install_requirements(env: dict[str, str]) -> None:
    _require_file(GUI_REQUIREMENTS, "GUI requirements")

    python_bin = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / "python"
    pip_base_cmd = [str(python_bin), "-m", "pip", "install", "--no-cache-dir", "--index-url", PYPI_INDEX_URL]
    run([*pip_base_cmd, "-r", str(GUI_REQUIREMENTS)], env=env)


def main() -> None:
    args = parse_args()
    ensure_supported_python()
    env = build_hermetic_env()
    create_or_recreate_venv(args.recreate, env)
    install_requirements(env)
    print("[bootstrap] Complete.")


if __name__ == "__main__":
    main()
