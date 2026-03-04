from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import bootstrap


def test_bootstrap_installs_only_gui_requirements(monkeypatch) -> None:
    commands: list[list[str]] = []
    required_files: list[Path] = []

    def fake_require_file(path: Path, description: str) -> None:
        required_files.append(path)

    monkeypatch.setattr(bootstrap, "_require_file", fake_require_file)

    def fake_run(command, env):
        commands.append(command)

    monkeypatch.setattr(bootstrap, "run", fake_run)

    bootstrap.install_requirements(env={})

    assert required_files == [bootstrap.GUI_REQUIREMENTS]
    assert len(commands) == 1
    assert commands[0][-2:] == ["-r", str(bootstrap.GUI_REQUIREMENTS)]


def test_bootstrap_source_has_no_inference_install_or_fetch_logic() -> None:
    source = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap.py"
    text = source.read_text(encoding="utf-8")

    assert "fetch_sd_infer.py" not in text
    assert "source/sd-inference-server/requirements.txt" not in text
    assert "source/requirements_inference.txt" not in text
    assert "requirements/inference-server.txt" not in text
    assert "inference-base.txt" not in text
    assert "--mode" not in text


def test_compatibility_probe_uses_single_requirements_download_call(monkeypatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setattr(bootstrap, "_require_file", lambda path, description: None)

    def fake_subprocess_run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(bootstrap.subprocess, "run", fake_subprocess_run)

    bootstrap.probe_pinned_compatibility(env={})

    assert len(commands) == 1
    assert "download" in commands[0]
    assert "-r" in commands[0]
    requirements_index = commands[0].index("-r") + 1
    assert commands[0][requirements_index] == str(bootstrap.GUI_REQUIREMENTS)


def test_compatibility_probe_failure_reports_single_pip_snippet(monkeypatch) -> None:
    monkeypatch.setattr(bootstrap, "_require_file", lambda path, description: None)

    def fake_subprocess_run(command, **kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout="Collecting pinned-package==1.0\nERROR: No matching distribution found for pinned-package==1.0\n",
            stderr="",
        )

    monkeypatch.setattr(bootstrap.subprocess, "run", fake_subprocess_run)

    try:
        bootstrap.probe_pinned_compatibility(env={})
    except bootstrap.CompatibilityProbeError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected CompatibilityProbeError")

    assert "COMPATIBILITY PROBE FAILED" in message
    assert "requirements_file=" in message
    assert "pip_command=" in message
    assert "No matching distribution found" in message
