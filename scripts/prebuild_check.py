#!/usr/bin/env python3
"""Build gate checks that must pass before producing distributable binaries."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from env_common import REPO_ROOT, build_env, venv_python

DEFAULT_SMOKE_TESTS = [
    "tests/test_env_sanity.py",
    "tests/test_qml_load.py",
]

PYQT_IMPORT_PATTERNS = (
    "import PyQt5",
    "from PyQt5",
)


def _run_python(args: list[str], *, label: str, extra_env: dict[str, str] | None = None) -> None:
    cmd = [str(venv_python()), *args]
    env = build_env(extra_env)
    print(f"[prebuild] {label}: $ {' '.join(cmd)}")
    completed = subprocess.run(cmd, cwd=REPO_ROOT, env=env, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"{label} failed with exit code {completed.returncode}")


def _assert_no_pyqt5_imports() -> None:
    excluded_dirs = {".git", ".venv", ".tmp", ".third_party", "__pycache__"}
    violations: list[str] = []
    for path in REPO_ROOT.rglob("*.py"):
        if excluded_dirs.intersection(path.parts):
            continue
        if path.name == "prebuild_check.py":
            continue
        content = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if any(pattern in stripped for pattern in PYQT_IMPORT_PATTERNS):
                rel_path = path.relative_to(REPO_ROOT)
                violations.append(f"{rel_path}:{line_no}: {stripped}")

    if violations:
        joined = "\n".join(sorted(violations))
        raise SystemExit("Found forbidden PyQt5 imports:\n" + joined)
    print("[prebuild] PyQt5 import guard passed.")


def _assert_sd_inference_server_present() -> None:
    server_root = REPO_ROOT / ".third_party" / "sd-inference-server"
    git_dir = server_root / ".git"
    server_entrypoint = server_root / "server.py"
    if not server_root.is_dir() or not server_entrypoint.is_file():
        raise SystemExit(
            "Missing .third_party/sd-inference-server. Run `python scripts/fetch_sd_infer.py` before building."
        )
    if not git_dir.exists():
        raise SystemExit(".third_party/sd-inference-server exists but is not a git checkout/submodule (.git missing).")
    print("[prebuild] sd-inference-server checkout present.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pytest-args",
        nargs="*",
        default=DEFAULT_SMOKE_TESTS,
        help="Pytest targets/args for smoke test execution (default: env + qml smoke tests).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _run_python(["scripts/qml_audit.py"], label="QML audit")
    _run_python(
        ["-m", "pytest", *args.pytest_args],
        label="pytest smoke",
        extra_env={"QT_QPA_PLATFORM": "offscreen", "QDIFFUSION_QML_SMOKE_ARGS": "--no-effects"},
    )
    _assert_no_pyqt5_imports()
    _assert_sd_inference_server_present()
    print("[prebuild] all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
