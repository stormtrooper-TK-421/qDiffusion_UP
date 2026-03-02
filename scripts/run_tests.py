#!/usr/bin/env python3
"""Run pytest with hermetic env and GUI-safe defaults."""

from __future__ import annotations

import sys

from env_common import run_with_venv


if __name__ == "__main__":
    extra_env = {
        "QT_QPA_PLATFORM": "offscreen",
        "QDIFFUSION_QML_SMOKE_ARGS": "--no-effects",
    }
    pytest_args = sys.argv[1:] or ["tests"]
    raise SystemExit(run_with_venv(["-m", "pytest", *pytest_args], extra_env=extra_env))
