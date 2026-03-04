#!/usr/bin/env python3
"""Validate repository requirement-file layout invariants.

Rules enforced:
- GUI dependencies must be defined only in requirements/gui.txt.
- Additional GUI requirement files are forbidden anywhere else in the repository.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_GUI_REQUIREMENTS = REPO_ROOT / "requirements" / "gui.txt"
EXCLUDED_DIRS = {".git", ".venv", ".tmp", ".third_party", "__pycache__"}


def _is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.parts)


def _looks_like_gui_requirements(path: Path) -> bool:
    filename = path.name.lower()

    if filename == "requirements_gui.txt":
        return True
    if filename.startswith("gui") and filename.endswith("requirements.txt"):
        return True
    if filename.startswith("requirements") and "gui" in filename and filename.endswith(".txt"):
        return True

    parent_name = path.parent.name.lower()
    if parent_name == "requirements" and filename.endswith(".txt") and "gui" in filename:
        return True

    return "gui" in filename and "requirement" in filename and filename.endswith(".txt")


def main() -> int:
    if not CANONICAL_GUI_REQUIREMENTS.is_file():
        raise SystemExit(f"Missing canonical GUI requirements file: {CANONICAL_GUI_REQUIREMENTS.relative_to(REPO_ROOT)}")

    violations: list[Path] = []
    for path in REPO_ROOT.rglob("*.txt"):
        if _is_excluded(path):
            continue
        if path.resolve() == CANONICAL_GUI_REQUIREMENTS.resolve():
            continue
        if _looks_like_gui_requirements(path):
            violations.append(path.relative_to(REPO_ROOT))

    if violations:
        formatted = "\n".join(f"- {path.as_posix()}" for path in sorted(violations))
        raise SystemExit(
            "Found forbidden GUI requirements file(s). "
            "Use requirements/gui.txt as the single source of truth:\n"
            f"{formatted}"
        )

    print("[requirements-layout] OK: requirements/gui.txt is the only GUI requirements file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
