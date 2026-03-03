from __future__ import annotations

import types

import runtime_requirements


def test_missing_python_requirements_supports_core_specifiers(monkeypatch) -> None:
    installed_versions = {
        "ok-eq": "1.2.3",
        "ok-range": "2.5.0",
        "ok-ne": "1.0.1",
        "missing-upper": "4.0.0",
    }

    def fake_distribution(name: str):
        if name not in installed_versions:
            raise runtime_requirements.PackageNotFoundError
        return types.SimpleNamespace(version=installed_versions[name])

    monkeypatch.setattr(runtime_requirements, "distribution", fake_distribution)

    missing = runtime_requirements.missing_python_requirements(
        [
            "ok-eq==1.2.3",
            "ok-range>=2.0,<3.0",
            "ok-ne!=1.0.0",
            "missing-upper<4.0.0",
            "missing-dist>=1.0.0",
        ],
        enforce_version=True,
    )

    assert missing == ["missing-upper<4.0.0", "missing-dist>=1.0.0"]


def test_missing_python_requirements_supports_compatible_release(monkeypatch) -> None:
    def fake_distribution(name: str):
        assert name == "example"
        return types.SimpleNamespace(version="1.4.5")

    monkeypatch.setattr(runtime_requirements, "distribution", fake_distribution)

    assert runtime_requirements.missing_python_requirements(["example~=1.4.0"], enforce_version=True) == []
    assert runtime_requirements.missing_python_requirements(["example~=1.5.0"], enforce_version=True) == ["example~=1.5.0"]


def test_missing_python_requirements_ignores_unparseable_requirements(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_requirements,
        "distribution",
        lambda name: types.SimpleNamespace(version="1.0.0"),
    )

    assert runtime_requirements.missing_python_requirements(["not a requirement ???"], enforce_version=True) == []
