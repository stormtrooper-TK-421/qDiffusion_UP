from __future__ import annotations

from pathlib import Path

import sync_infer_requirements


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_sync_script_updates_canonical_file_from_source(tmp_path, monkeypatch) -> None:
    source_requirements = tmp_path / "source" / "sd-inference-server" / "requirements.txt"
    canonical_requirements = tmp_path / "requirements" / "inference-server.txt"
    source_requirements.parent.mkdir(parents=True, exist_ok=True)
    source_requirements.write_text("one==1.0\n\n# comment\ntwo==2.0\n", encoding="utf-8")

    monkeypatch.setattr(sync_infer_requirements, "SOURCE_REQUIREMENTS", source_requirements)
    monkeypatch.setattr(sync_infer_requirements, "CANONICAL_REQUIREMENTS", canonical_requirements)
    monkeypatch.setattr(sync_infer_requirements, "REPO_ROOT", tmp_path)

    changed = sync_infer_requirements.sync_infer_requirements()

    assert changed is True
    output = canonical_requirements.read_text(encoding="utf-8")
    assert "Auto-generated from source/sd-inference-server/requirements.txt" in output
    assert "one==1.0" in output
    assert "two==2.0" in output


def test_sync_script_is_idempotent(tmp_path, monkeypatch) -> None:
    source_requirements = tmp_path / "source" / "sd-inference-server" / "requirements.txt"
    canonical_requirements = tmp_path / "requirements" / "inference-server.txt"
    source_requirements.parent.mkdir(parents=True, exist_ok=True)
    source_requirements.write_text("one==1.0\n", encoding="utf-8")

    monkeypatch.setattr(sync_infer_requirements, "SOURCE_REQUIREMENTS", source_requirements)
    monkeypatch.setattr(sync_infer_requirements, "CANONICAL_REQUIREMENTS", canonical_requirements)
    monkeypatch.setattr(sync_infer_requirements, "REPO_ROOT", tmp_path)

    assert sync_infer_requirements.sync_infer_requirements() is True
    assert sync_infer_requirements.sync_infer_requirements() is False


def test_inference_requirements_are_synced_during_preflight_and_updates_only() -> None:
    launch_source = (REPO_ROOT / "source" / "launch.py").read_text(encoding="utf-8")
    main_source = (REPO_ROOT / "source" / "main.py").read_text(encoding="utf-8")
    settings_source = (REPO_ROOT / "source" / "tabs" / "settings" / "settings.py").read_text(encoding="utf-8")
    bootstrap_source = (REPO_ROOT / "scripts" / "bootstrap.py").read_text(encoding="utf-8")

    assert "name=\"inference requirements sync\"" in launch_source
    assert "sync_infer_requirements.py" in main_source
    assert "inference-server.txt" in main_source
    assert "sync_infer_requirements.py" in settings_source

    assert "inference-server.txt" not in bootstrap_source
    assert "inference-base.txt" not in bootstrap_source
    assert "fetch_sd_infer.py" not in bootstrap_source
