#!/usr/bin/env python3
"""Run the vendored inference server on localhost:28888 with sanitized env."""

from __future__ import annotations

from env_common import run_with_venv


if __name__ == "__main__":
    raise SystemExit(
        run_with_venv(
            [
                "source/sd-inference-server/server.py",
                "--host",
                "127.0.0.1",
                "--port",
                "28888",
            ]
        )
    )
