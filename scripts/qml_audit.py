#!/usr/bin/env python3
"""Static and runtime QML audit checks used by prebuild validation."""

from __future__ import annotations

import subprocess
from pathlib import Path

from env_common import REPO_ROOT, build_env, venv_python


def _assert_no_file_qml_urls() -> None:
    violations: list[str] = []
    for qml_file in (REPO_ROOT / "source" / "qml").rglob("*.qml"):
        content = qml_file.read_text(encoding="utf-8")
        for line_no, line in enumerate(content.splitlines(), start=1):
            if "file:" in line:
                rel = qml_file.relative_to(REPO_ROOT)
                violations.append(f"{rel}:{line_no}: {line.strip()}")

    if violations:
        raise SystemExit("QML file URL usage is not allowed:\n" + "\n".join(violations))


def _run_qml_smoke() -> None:
    cmd = [str(venv_python()), "scripts/qml_smoke_test.py"]
    env = build_env({"QT_QPA_PLATFORM": "offscreen"})
    print(f"[qml-audit] $ {' '.join(cmd)}")
    completed = subprocess.run(cmd, cwd=REPO_ROOT, env=env, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"qml_smoke_test failed with exit code {completed.returncode}")


def main() -> int:
    _assert_no_file_qml_urls()
    _run_qml_smoke()
    print("[qml-audit] audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
