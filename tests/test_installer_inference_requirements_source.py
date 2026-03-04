from __future__ import annotations

import ast
from pathlib import Path


MAIN_PY = Path(__file__).resolve().parents[1] / "source" / "main.py"
CANONICAL_REQUIREMENTS_CONST = "INFERENCE_SERVER_REQUIREMENTS"
FORBIDDEN_REFERENCES = {
    "source/sd-inference-server/requirements.txt",
}


def _get_coordinator_find_needed_source() -> str:
    source = MAIN_PY.read_text(encoding="utf-8")
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == "Coordinator":
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name == "find_needed":
                    snippet = ast.get_source_segment(source, child)
                    assert snippet is not None
                    return snippet
    raise AssertionError("Coordinator.find_needed not found")


def test_coordinator_inference_planning_reads_only_canonical_synced_requirements() -> None:
    find_needed_source = _get_coordinator_find_needed_source()

    assert CANONICAL_REQUIREMENTS_CONST in find_needed_source
    assert "_load_requirements(INFERENCE_SERVER_REQUIREMENTS)" in find_needed_source

    for forbidden in FORBIDDEN_REFERENCES:
        assert forbidden not in find_needed_source
