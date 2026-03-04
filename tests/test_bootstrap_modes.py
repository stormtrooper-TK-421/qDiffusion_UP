from __future__ import annotations

from pathlib import Path

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
