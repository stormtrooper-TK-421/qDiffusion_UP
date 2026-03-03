from __future__ import annotations

from pathlib import Path
import types

import launch


def test_launch_uses_gui_requirements_file_path() -> None:
    assert launch.GUI_REQUIREMENTS_PATH == launch.REPO_ROOT / "requirements" / "gui.txt"


def test_gui_requirements_pin_bson_dependency() -> None:
    requirements = (Path(__file__).resolve().parents[1] / "requirements" / "gui.txt").read_text(encoding="utf-8")
    assert any(line.strip().startswith("bson") for line in requirements.splitlines())


def test_missing_gui_requirements_trigger_bootstrap(monkeypatch) -> None:
    monkeypatch.setattr(launch, "_is_inside_expected_venv", lambda: True)
    monkeypatch.setattr(launch, "_load_requirements", lambda path: ["bson==0.5.10"])

    state = {"bootstrapped": False}

    def fake_missing_python_requirements(requirements, enforce_version):
        assert requirements == ["bson==0.5.10"]
        assert enforce_version is True
        if not state["bootstrapped"]:
            return ["bson==0.5.10"]
        return []

    def fake_run(command, check=False):
        assert command == [
            launch.sys.executable,
            str(launch.REPO_ROOT / "scripts" / "bootstrap.py"),
            "--mode",
            "gui",
        ]
        state["bootstrapped"] = True
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(launch, "missing_python_requirements", fake_missing_python_requirements)
    monkeypatch.setattr(launch.subprocess, "run", fake_run)

    launch._ensure_runtime_requirements()
    assert state["bootstrapped"] is True


def test_failed_bootstrap_raises_runtime_error(monkeypatch) -> None:
    monkeypatch.setattr(launch, "_is_inside_expected_venv", lambda: True)
    monkeypatch.setattr(launch, "_load_requirements", lambda path: ["bson==0.5.10"])

    monkeypatch.setattr(
        launch,
        "missing_python_requirements",
        lambda requirements, enforce_version: ["bson==0.5.10"],
    )
    monkeypatch.setattr(
        launch.subprocess,
        "run",
        lambda command, check=False: types.SimpleNamespace(returncode=1),
    )

    try:
        launch._ensure_runtime_requirements()
    except RuntimeError as exc:
        assert str(exc) == (
            "Failed to bootstrap GUI dependencies. "
            "Missing requirements before bootstrap: bson==0.5.10."
        )
    else:
        raise AssertionError("Expected RuntimeError was not raised")


def test_missing_gui_requirements_after_bootstrap_raise_runtime_error(monkeypatch) -> None:
    monkeypatch.setattr(launch, "_is_inside_expected_venv", lambda: True)
    monkeypatch.setattr(launch, "_load_requirements", lambda path: ["bson==0.5.10", "PySide6==6.10.2"])
    monkeypatch.setattr(
        launch,
        "missing_python_requirements",
        lambda requirements, enforce_version: ["PySide6==6.10.2"],
    )
    monkeypatch.setattr(
        launch.subprocess,
        "run",
        lambda command, check=False: types.SimpleNamespace(returncode=0),
    )

    try:
        launch._ensure_runtime_requirements()
    except RuntimeError as exc:
        assert str(exc) == (
            "GUI runtime requirements are still missing after bootstrap: PySide6==6.10.2. "
            "Run scripts/bootstrap.py --mode gui to reinstall GUI dependencies."
        )
    else:
        raise AssertionError("Expected RuntimeError was not raised")
