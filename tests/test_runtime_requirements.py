from __future__ import annotations

import types

import runtime_requirements


def test_missing_python_requirements_detects_missing_distributions(monkeypatch) -> None:
    installed = {"present", "with-extra", "versioned"}

    def fake_distribution(name: str):
        if name not in installed:
            raise runtime_requirements.PackageNotFoundError
        return types.SimpleNamespace(version="1.0.0")

    monkeypatch.setattr(runtime_requirements, "distribution", fake_distribution)

    missing = runtime_requirements.missing_python_requirements(
        [
            "present",
            "with-extra[foo]>=1.0",
            "versioned==2.0.0",
            "absent>=0.1",
        ],
        enforce_version=True,
    )

    assert missing == ["absent>=0.1"]


def test_missing_python_requirements_ignores_non_requirement_lines(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_requirements,
        "distribution",
        lambda name: types.SimpleNamespace(version="1.0.0"),
    )

    assert runtime_requirements.missing_python_requirements(["", "# comment"], enforce_version=True) == []
