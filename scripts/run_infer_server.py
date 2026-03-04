#!/usr/bin/env python3
"""Run the vendored inference server on localhost:28888 with sanitized env."""

from __future__ import annotations

from pathlib import Path

from env_common import REPO_ROOT, run_with_venv

FETCH_SCRIPT = Path("scripts/fetch_sd_infer.py")
INFER_SERVER = Path("source/sd-inference-server/server.py")


def ensure_infer_server_present() -> None:
    fetch_rc = run_with_venv([str(FETCH_SCRIPT)])
    if fetch_rc != 0:
        raise SystemExit(fetch_rc)

    server_path = REPO_ROOT / INFER_SERVER
    if not server_path.is_file():
        raise SystemExit(f"Missing inference server entrypoint after fetch: {server_path}")


if __name__ == "__main__":
    ensure_infer_server_present()
    models_dir = (REPO_ROOT / "models").resolve()
    models_dir.mkdir(parents=True, exist_ok=True)
    raise SystemExit(
        run_with_venv(
            [
                str(INFER_SERVER),
                "--bind",
                "127.0.0.1:28888",
                "--models",
                str(models_dir),
            ]
        )
    )
