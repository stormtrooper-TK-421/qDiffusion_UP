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
    parser.add_argument("--timeout", type=float, default=25.0, help="Max startup wait in seconds (default: 25)")
    return parser.parse_args()


def _tail_since(path: Path, offset: int) -> tuple[int, str]:
    if not path.exists():
        return offset, ""
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        handle.seek(offset)
        chunk = handle.read()
        return handle.tell(), chunk


def main() -> int:
    args = parse_args()
    exe_path = (REPO_ROOT / args.exe_path).resolve() if not Path(args.exe_path).is_absolute() else Path(args.exe_path)
    if not exe_path.is_file():
        raise SystemExit(f"Executable not found: {exe_path}")

    log_dir = REPO_ROOT / ".logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    boot_log = log_dir / "boot.log"
    launcher_crash_log = exe_path.parent / "launcher_crash.log"
    crash_log = exe_path.parent / "crash.log"

    launcher_offset = launcher_crash_log.stat().st_size if launcher_crash_log.exists() else 0
    crash_offset = crash_log.stat().st_size if crash_log.exists() else 0

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

    preflight_healthy = False
    launcher_chunk = ""
    crash_chunk = ""
    try:
        while time.time() - started_at < args.timeout:
            launcher_offset, latest_launcher = _tail_since(launcher_crash_log, launcher_offset)
            crash_offset, latest_crash = _tail_since(crash_log, crash_offset)
            if latest_launcher:
                launcher_chunk += latest_launcher
            if latest_crash:
                crash_chunk += latest_crash

            if "[python exit] ExitCode=" in launcher_chunk and "[python exit] ExitCode=0" not in launcher_chunk:
                raise SystemExit("Launcher reported non-zero python child exit in launcher_crash.log")

            if "Preflight stage failed:" in crash_chunk or "[FAIL] GUI dependency validation" in crash_chunk:
                raise SystemExit("Detected launch preflight failure in crash.log")

            if "[OK] GUI dependency validation: stage completed" in crash_chunk:
                preflight_healthy = True
                break

            if process.poll() is not None:
                raise SystemExit(f"Process exited before healthy preflight state. exit={process.returncode}")
            time.sleep(0.1)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

    if not preflight_healthy:
        raise SystemExit(
            "Process did not reach healthy preflight state before timeout. "
            f"timeout={args.timeout}s exe={exe_path}"
        )

    with boot_log.open("a", encoding="utf-8") as handle:
        handle.write(f"boot ok: {exe_path} --no-effects\n")
    print(f"[postbuild] boot ok recorded at {boot_log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
