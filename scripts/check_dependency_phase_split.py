#!/usr/bin/env python3
"""Validate GUI vs inference dependency phase split invariants.

Phase A (bootstrap/launch):
- Reads only requirements/gui.txt.
- Must not pull inference dependencies.

Phase B (installer planning):
- Reads only requirements/inference-server.txt.
- Must not reference legacy inference-base sources.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GUI_REQUIREMENTS = REPO_ROOT / "requirements" / "gui.txt"
INFERENCE_REQUIREMENTS = REPO_ROOT / "requirements" / "inference-server.txt"
INSTALLER_PLANNING_FILE = REPO_ROOT / "source" / "main.py"
PHASE_A_FILES = (
    REPO_ROOT / "scripts" / "bootstrap.py",
    REPO_ROOT / "source" / "launch.py",
)

INFERENCE_ONLY_DEPENDENCIES = {
    "accelerate",
    "diffusers",
    "k_diffusion",
    "segment-anything",
    "timm",
    "transformers",
    "ultralytics",
}

FORBIDDEN_PHASE_A_REFERENCES = (
    "requirements/inference-server.txt",
    "requirements/inference-base.txt",
    "source/sd-inference-server/requirements.txt",
)

FORBIDDEN_INSTALLER_REFERENCES = (
    "requirements/inference-base.txt",
    "source/sd-inference-server/requirements.txt",
    "INFERENCE_BASE_REQUIREMENTS",
)


def _parse_requirement_names(path: Path) -> set[str]:
    names: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith(("-r", "--", "-f", "-c")):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)", line)
        if match:
            names.add(match.group(1).lower())
    return names


def _validate_requirement_files() -> list[str]:
    issues: list[str] = []
    if not GUI_REQUIREMENTS.is_file():
        issues.append(
            f"missing canonical GUI requirements source: {GUI_REQUIREMENTS.relative_to(REPO_ROOT).as_posix()}"
        )
    if not INFERENCE_REQUIREMENTS.is_file():
        issues.append(
            "missing canonical inference requirements source: "
            f"{INFERENCE_REQUIREMENTS.relative_to(REPO_ROOT).as_posix()}"
        )
        return issues

    gui_names = _parse_requirement_names(GUI_REQUIREMENTS)
    inference_names = _parse_requirement_names(INFERENCE_REQUIREMENTS)

    offenders_in_gui = sorted(INFERENCE_ONLY_DEPENDENCIES.intersection(gui_names))
    if offenders_in_gui:
        issues.append(
            "inference-only dependencies found in Phase A GUI requirements "
            f"({GUI_REQUIREMENTS.relative_to(REPO_ROOT).as_posix()}): {', '.join(offenders_in_gui)}"
        )

    missing_from_inference = sorted(INFERENCE_ONLY_DEPENDENCIES.difference(inference_names))
    if missing_from_inference:
        issues.append(
            "expected inference-only dependencies missing from canonical Phase B source "
            f"({INFERENCE_REQUIREMENTS.relative_to(REPO_ROOT).as_posix()}): "
            f"{', '.join(missing_from_inference)}"
        )

    return issues


def _validate_phase_a_sources() -> list[str]:
    issues: list[str] = []
    for path in PHASE_A_FILES:
        rel_path = path.relative_to(REPO_ROOT).as_posix()
        content = path.read_text(encoding="utf-8")

        has_gui_reference = "requirements/gui.txt" in content or "GUI_REQUIREMENTS_PATH" in content
        if not has_gui_reference:
            issues.append(f"{rel_path}: missing explicit Phase A GUI requirements reference (requirements/gui.txt or GUI_REQUIREMENTS_PATH)")

        forbidden_found = [entry for entry in FORBIDDEN_PHASE_A_REFERENCES if entry in content]
        if forbidden_found:
            issues.append(
                f"{rel_path}: forbidden Phase B dependency source reference(s): {', '.join(sorted(forbidden_found))}"
            )
    return issues


def _validate_installer_planning_source() -> list[str]:
    issues: list[str] = []
    rel_path = INSTALLER_PLANNING_FILE.relative_to(REPO_ROOT).as_posix()
    content = INSTALLER_PLANNING_FILE.read_text(encoding="utf-8")

    if "INFERENCE_SERVER_REQUIREMENTS" not in content:
        issues.append(f"{rel_path}: missing INFERENCE_SERVER_REQUIREMENTS constant usage")

    if "_load_requirements(INFERENCE_SERVER_REQUIREMENTS)" not in content:
        issues.append(
            f"{rel_path}: installer planning does not load requirements via _load_requirements(INFERENCE_SERVER_REQUIREMENTS)"
        )

    forbidden_found = [entry for entry in FORBIDDEN_INSTALLER_REFERENCES if entry in content]
    if forbidden_found:
        issues.append(
            f"{rel_path}: forbidden installer-planning inference source reference(s): "
            f"{', '.join(sorted(forbidden_found))}"
        )

    return issues


def main() -> int:
    issues = [
        *_validate_requirement_files(),
        *_validate_phase_a_sources(),
        *_validate_installer_planning_source(),
    ]
    if issues:
        formatted = "\n".join(f"- {issue}" for issue in issues)
        raise SystemExit(
            "Dependency phase split check failed.\n"
            "Phase A = bootstrap/launch GUI prerequisites (requirements/gui.txt only).\n"
            "Phase B = installer-planned inference dependencies (requirements/inference-server.txt).\n"
            f"Violations:\n{formatted}"
        )

    print("[dependency-phase-split] OK: Phase A/B dependency boundaries are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
