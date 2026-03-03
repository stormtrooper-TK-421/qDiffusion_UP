from __future__ import annotations

from pathlib import Path

import launch


def test_launch_checks_for_bson_runtime_module() -> None:
    assert "bson" in launch.REQUIRED_GUI_MODULES


def test_gui_requirements_pin_bson_dependency() -> None:
    requirements = (Path(__file__).resolve().parents[1] / "requirements" / "gui.txt").read_text(encoding="utf-8")
    assert any(line.strip().startswith("bson") for line in requirements.splitlines())
