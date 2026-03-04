from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_dependency_phase_split.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("check_dependency_phase_split", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dependency_phase_split_check_passes_for_repository_state() -> None:
    module = _load_script_module()
    assert module.main() == 0
