from __future__ import annotations

from pathlib import Path
import types

import launch


def test_launch_uses_gui_requirements_file_path() -> None:
    assert launch.GUI_REQUIREMENTS_PATH == launch.REPO_ROOT / "requirements" / "gui.txt"


def test_gui_requirements_pin_bson_dependency() -> None:
    requirements = (Path(__file__).resolve().parents[1] / "requirements" / "gui.txt").read_text(encoding="utf-8")
    assert any(line.strip().startswith("bson") for line in requirements.splitlines())


def test_gui_requirements_do_not_include_torch_or_diffusers_stack() -> None:
    requirements = (Path(__file__).resolve().parents[1] / "requirements" / "gui.txt").read_text(encoding="utf-8")
    packages = {line.split("#", 1)[0].strip().lower() for line in requirements.splitlines() if line.strip()}
    assert all(not entry.startswith("torch") for entry in packages)
    assert all(not entry.startswith("diffusers") for entry in packages)


def test_launch_runtime_requirement_check_is_gui_only() -> None:
    launch_source = (Path(__file__).resolve().parents[1] / "source" / "launch.py").read_text(encoding="utf-8")
    assert "GUI_REQUIREMENTS_PATH" in launch_source
    assert "gui.txt" in launch_source


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

    def fake_run(command, check=False, **kwargs):
        assert command == [
            launch.sys.executable,
            str(launch.REPO_ROOT / "scripts" / "bootstrap.py"),
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
        lambda command, check=False, **kwargs: types.SimpleNamespace(returncode=1, stdout="", stderr=""),
    )

    try:
        launch._ensure_runtime_requirements()
    except RuntimeError as exc:
        message = str(exc)
        assert "Failed to bootstrap GUI dependencies." in message
        assert "Missing requirements before bootstrap: bson==0.5.10." in message
        assert "bootstrap stdout:" in message
        assert "bootstrap stderr:" in message
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
        lambda command, check=False, **kwargs: types.SimpleNamespace(returncode=0),
    )

    try:
        launch._ensure_runtime_requirements()
    except RuntimeError as exc:
        assert str(exc) == (
            "GUI runtime requirements are still missing after bootstrap: PySide6==6.10.2. "
            "Run scripts/bootstrap.py to reinstall GUI dependencies."
        )
    else:
        raise AssertionError("Expected RuntimeError was not raised")
