from __future__ import annotations

import bootstrap


def test_gui_mode_only_installs_gui_requirements(monkeypatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setattr(bootstrap, "_require_file", lambda path, description: None)
    monkeypatch.setattr(bootstrap, "ensure_infer_server_checkout", lambda env: (_ for _ in ()).throw(AssertionError("infer checkout should not run")))
    monkeypatch.setattr(bootstrap, "_require_infer_requirements", lambda: (_ for _ in ()).throw(AssertionError("infer requirements should not run")))

    def fake_run(command, env):
        commands.append(command)

    monkeypatch.setattr(bootstrap, "run", fake_run)

    bootstrap.install_requirements("gui", env={})

    assert len(commands) == 1
    assert commands[0][-2:] == ["-r", str(bootstrap.GUI_REQUIREMENTS)]


def test_infer_mode_installs_inference_base_and_server_requirements(monkeypatch) -> None:
    commands: list[list[str]] = []
    infer_checkout_called = {"called": False}

    monkeypatch.setattr(bootstrap, "_require_file", lambda path, description: None)
    monkeypatch.setattr(bootstrap, "_require_infer_requirements", lambda: None)

    def fake_checkout(env):
        infer_checkout_called["called"] = True

    def fake_run(command, env):
        commands.append(command)

    monkeypatch.setattr(bootstrap, "ensure_infer_server_checkout", fake_checkout)
    monkeypatch.setattr(bootstrap, "run", fake_run)

    bootstrap.install_requirements("infer", env={})

    assert infer_checkout_called["called"] is True
    assert len(commands) == 2
    assert commands[0][-2:] == ["-r", str(bootstrap.INFERENCE_BASE_REQUIREMENTS)]
    assert commands[1][-2:] == ["-r", str(bootstrap.INFER_REQUIREMENTS)]
