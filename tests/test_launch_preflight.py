from __future__ import annotations

import re

import pytest

import launch


def test_preflight_pipeline_runs_stages_in_order(monkeypatch) -> None:
    events: list[str] = []

    def stage(name: str):
        def _runner() -> None:
            events.append(f"run:{name}")

        return _runner

    monkeypatch.setattr(
        launch,
        "PREFLIGHT_STAGES",
        (
            launch.PreflightStage("one", stage("one"), "fix-one"),
            launch.PreflightStage("two", stage("two"), "fix-two"),
            launch.PreflightStage("three", stage("three"), "fix-three"),
        ),
    )

    log_events: list[tuple[str, str]] = []

    def fake_log(stage_name: str, status: str, message: str, remediation: str | None = None) -> None:
        log_events.append((stage_name, status))

    monkeypatch.setattr(launch, "_log_preflight", fake_log)

    launch.run_preflight_pipeline()

    assert events == ["run:one", "run:two", "run:three"]
    assert log_events == [
        ("one", "START"),
        ("one", "OK"),
        ("two", "START"),
        ("two", "OK"),
        ("three", "START"),
        ("three", "OK"),
    ]


@pytest.mark.parametrize("failing_stage", [0, 1, 2, 3])
def test_preflight_pipeline_fails_fast_at_first_broken_stage(monkeypatch, failing_stage: int) -> None:
    run_order: list[str] = []

    def make_stage(index: int):
        def _runner() -> None:
            run_order.append(f"stage-{index}")
            if index == failing_stage:
                raise RuntimeError(f"broken-{index}")

        return _runner

    stages = tuple(
        launch.PreflightStage(
            launch.PREFLIGHT_STAGES[index].name,
            make_stage(index),
            launch.PREFLIGHT_STAGES[index].remediation,
        )
        for index in range(len(launch.PREFLIGHT_STAGES))
    )

    monkeypatch.setattr(launch, "PREFLIGHT_STAGES", stages)

    log_events: list[tuple[str, str]] = []

    def fake_log(stage_name: str, status: str, message: str, remediation: str | None = None) -> None:
        log_events.append((stage_name, status))

    monkeypatch.setattr(launch, "_log_preflight", fake_log)

    expected = re.escape(f"Preflight stage failed: {stages[failing_stage].name}. broken-{failing_stage}")
    with pytest.raises(RuntimeError, match=expected):
        launch.run_preflight_pipeline()

    assert run_order == [f"stage-{i}" for i in range(failing_stage + 1)]
    expected_log_events: list[tuple[str, str]] = []
    for index in range(failing_stage):
        expected_log_events.extend([(stages[index].name, "START"), (stages[index].name, "OK")])
    expected_log_events.extend([(stages[failing_stage].name, "START"), (stages[failing_stage].name, "FAIL")])
    assert log_events == expected_log_events
