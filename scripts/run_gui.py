#!/usr/bin/env python3
"""Run the GUI launcher under the repository's hermetic runtime environment."""

from __future__ import annotations

import sys

from env_common import run_with_venv


if __name__ == "__main__":
    raise SystemExit(run_with_venv(["source/launch.py", *sys.argv[1:]]))
