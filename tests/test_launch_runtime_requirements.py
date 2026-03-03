from __future__ import annotations

from pathlib import Path
import types

import launch


def test_launch_checks_for_gui_runtime_modules() -> None:
    assert "bson" in launch.REQUIRED_GUI_MODULES
    assert "PIL.Image" in launch.REQUIRED_GUI_MODULES
    assert "websockets.sync.client" in launch.REQUIRED_GUI_MODULES
    assert "cryptography.hazmat.primitives" in launch.REQUIRED_GUI_MODULES


def test_gui_requirements_pin_bson_dependency() -> None:
    requirements = (Path(__file__).resolve().parents[1] / "requirements" / "gui.txt").read_text(encoding="utf-8")
    assert any(line.strip().startswith("bson") for line in requirements.splitlines())


def test_missing_gui_modules_trigger_bootstrap(monkeypatch) -> None:
    monkeypatch.setattr(launch, "_is_inside_expected_venv", lambda: True)

    state = {"bootstrapped": False}

    def fake_missing_python_modules(modules):
        if modules == launch.REQUIRED_PYSIDE6_MODULES:
            return []
        if modules == launch.REQUIRED_GUI_MODULES and not state["bootstrapped"]:
            return ["bson"]
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

    monkeypatch.setattr(launch, "missing_python_modules", fake_missing_python_modules)
    monkeypatch.setattr(launch.subprocess, "run", fake_run)

    launch._ensure_runtime_requirements()
    assert state["bootstrapped"] is True


def test_failed_bootstrap_raises_runtime_error(monkeypatch) -> None:
    monkeypatch.setattr(launch, "_is_inside_expected_venv", lambda: True)

    def fake_missing_python_modules(modules):
        if modules == launch.REQUIRED_PYSIDE6_MODULES:
            return []
        if modules == launch.REQUIRED_GUI_MODULES:
            return ["bson"]
        return []

    monkeypatch.setattr(launch, "missing_python_modules", fake_missing_python_modules)
    monkeypatch.setattr(
        launch.subprocess,
        "run",
        lambda command, check=False: types.SimpleNamespace(returncode=1),
    )

    try:
        launch._ensure_runtime_requirements()
    except RuntimeError as exc:
        assert str(exc) == "Failed to bootstrap GUI dependencies."
    else:
        raise AssertionError("Expected RuntimeError was not raised")
