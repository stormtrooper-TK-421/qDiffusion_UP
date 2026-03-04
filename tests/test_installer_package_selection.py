from __future__ import annotations

import ast
from pathlib import Path


MAIN_PY = Path(__file__).resolve().parents[1] / "source" / "main.py"


def _get_coordinator_methods() -> tuple[str, str]:
    source = MAIN_PY.read_text(encoding="utf-8")
    module = ast.parse(source)

    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == "Coordinator":
            mode_backend = None
            get_needed = None
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name == "_mode_backend_needed":
                    mode_backend = ast.get_source_segment(source, child)
                if isinstance(child, ast.FunctionDef) and child.name == "get_needed":
                    get_needed = ast.get_source_segment(source, child)
            assert mode_backend is not None
            assert get_needed is not None
            return mode_backend, get_needed

    raise AssertionError("Coordinator class not found")


def _get_coordinator_method(name: str) -> str:
    source = MAIN_PY.read_text(encoding="utf-8")
    module = ast.parse(source)

    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == "Coordinator":
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name == name:
                    method_source = ast.get_source_segment(source, child)
                    assert method_source is not None
                    return method_source

    raise AssertionError(f"Coordinator.{name} not found")


def _build_get_needed(is_win: bool):
    mode_backend_source, get_needed_source = _get_coordinator_methods()
    namespace = {"IS_WIN": is_win}
    exec(mode_backend_source, namespace)
    exec(get_needed_source, namespace)
    return namespace["_mode_backend_needed"], namespace["get_needed"]


def _build_install_step_method(is_win: bool):
    build_steps_source = _get_coordinator_method("_build_install_steps")
    namespace = {
        "IS_WIN": is_win,
        "INFERENCE_SERVER_REQUIREMENTS": "requirements/inference-server.txt",
    }
    exec(build_steps_source, namespace)
    return namespace["_build_install_steps"]


def _coordinator_stub(mode: str):
    class Stub:
        pass

    coordinator = Stub()
    coordinator._modes = ["nvidia", "amd", "remote"]
    coordinator._mode = coordinator._modes.index(mode)
    coordinator.optional_need = ["diffusers==0.27.2", "accelerate==0.27.2"]
    coordinator.core = ["pip", "wheel", "PySide6"]
    coordinator.torch_version = "2.1.0"
    coordinator.torchvision_version = "0.16.0"
    coordinator.directml_version = ""
    coordinator.amd_torch_directml_version = "0.2.0.dev230426"
    return coordinator


def test_get_needed_does_not_include_gui_requirement_list() -> None:
    main_py = MAIN_PY.read_text(encoding="utf-8")
    get_needed_block = main_py.split("def get_needed(self):", 1)[1].split("@pyqtSlot()", 1)[0]

    assert "self.required_need" not in get_needed_block
    assert "self.optional_need" in get_needed_block
    assert '["pip", "wheel"]' not in get_needed_block


def test_get_needed_nvidia_is_inference_only() -> None:
    mode_backend, get_needed = _build_get_needed(is_win=False)
    coordinator = _coordinator_stub(mode="nvidia")
    coordinator._mode_backend_needed = lambda mode: mode_backend(coordinator, mode)

    needed = get_needed(coordinator)

    assert needed == ["diffusers==0.27.2", "accelerate==0.27.2"]
    assert "pip" not in needed
    assert "wheel" not in needed
    assert "PySide6" not in needed


def test_get_needed_amd_is_inference_only() -> None:
    mode_backend, get_needed = _build_get_needed(is_win=False)
    coordinator = _coordinator_stub(mode="amd")
    coordinator._mode_backend_needed = lambda mode: mode_backend(coordinator, mode)

    needed = get_needed(coordinator)

    assert needed == ["diffusers==0.27.2", "accelerate==0.27.2"]
    assert "pip" not in needed
    assert "wheel" not in needed
    assert "PySide6" not in needed


def test_get_needed_remote_only_contains_optional_inference_packages() -> None:
    mode_backend, get_needed = _build_get_needed(is_win=False)
    coordinator = _coordinator_stub(mode="remote")
    coordinator._mode_backend_needed = lambda mode: mode_backend(coordinator, mode)

    needed = get_needed(coordinator)

    assert needed == ["diffusers==0.27.2", "accelerate==0.27.2"]
    assert "pip" not in needed
    assert "wheel" not in needed
    assert "PySide6" not in needed


def test_mode_switching_changes_only_backend_delta() -> None:
    mode_backend, get_needed = _build_get_needed(is_win=False)

    nvidia = _coordinator_stub(mode="nvidia")
    nvidia._mode_backend_needed = lambda mode: mode_backend(nvidia, mode)

    amd = _coordinator_stub(mode="amd")
    amd._mode_backend_needed = lambda mode: mode_backend(amd, mode)

    remote = _coordinator_stub(mode="remote")
    remote._mode_backend_needed = lambda mode: mode_backend(remote, mode)

    nvidia_needed = get_needed(nvidia)
    amd_needed = get_needed(amd)
    remote_needed = get_needed(remote)

    assert nvidia_needed == amd_needed == remote_needed


def test_build_install_steps_uses_single_requirements_install() -> None:
    build_steps = _build_install_step_method(is_win=False)

    class Stub:
        pass

    coordinator = Stub()
    steps = build_steps(
        coordinator,
        "nvidia",
        ["torch-directml==0.2.0.dev230426"],
        ["diffusers==0.27.2", "accelerate==0.27.2"],
    )

    assert len(steps) == 2
    assert steps[0]["pip_args"] == [
        "pip",
        "install",
        "-U",
        "torch-directml==0.2.0.dev230426",
        "--progress-bar",
        "raw",
    ]
    assert steps[1]["pip_args"] == [
        "pip",
        "install",
        "-U",
        "-r",
        "requirements/inference-server.txt",
        "--progress-bar",
        "raw",
    ]


def test_build_install_steps_adds_windows_binary_only_flag_for_inference_requirements() -> None:
    build_steps = _build_install_step_method(is_win=True)

    class Stub:
        pass

    coordinator = Stub()
    steps = build_steps(
        coordinator,
        "amd",
        ["torch-directml==0.2.0.dev230426"],
        ["diffusers==0.27.2"],
    )

    assert len(steps) == 2
    assert "--index-url" not in steps[0]["pip_args"]
    assert "--only-binary=:all:" in steps[1]["pip_args"]
