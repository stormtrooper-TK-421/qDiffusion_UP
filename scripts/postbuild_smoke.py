#!/usr/bin/env python3
"""Launch a built executable as a post-build smoke test."""

from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path

from env_common import REPO_ROOT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "exe_path",
        nargs="?",
        default="qDiffusion.exe",
        help="Path to built executable (default: qDiffusion.exe)",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="Max startup wait in seconds (default: 10)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    exe_path = (REPO_ROOT / args.exe_path).resolve() if not Path(args.exe_path).is_absolute() else Path(args.exe_path)
    if not exe_path.is_file():
        raise SystemExit(f"Executable not found: {exe_path}")

    log_dir = REPO_ROOT / ".logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    boot_log = log_dir / "boot.log"

    cmd = [str(exe_path), "--no-effects"]
    print(f"[postbuild] launching: {' '.join(cmd)}")

    started_at = time.time()
    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(exe_path.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise SystemExit(f"Unable to launch executable {exe_path}: {exc}") from exc

    start_confirmed = False
    try:
        while time.time() - started_at < args.timeout:
            if process.poll() is None:
                start_confirmed = True
                break
            time.sleep(0.1)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

    if not start_confirmed:
        raise SystemExit(f"Process failed to remain alive during startup window: {exe_path}")

    with boot_log.open("a", encoding="utf-8") as handle:
        handle.write(f"boot ok: {exe_path} --no-effects\n")
    print(f"[postbuild] boot ok recorded at {boot_log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
