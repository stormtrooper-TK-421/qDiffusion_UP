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


def _build_get_needed(is_win: bool):
    mode_backend_source, get_needed_source = _get_coordinator_methods()
    namespace = {"IS_WIN": is_win}
    exec(mode_backend_source, namespace)
    exec(get_needed_source, namespace)
    return namespace["_mode_backend_needed"], namespace["get_needed"]


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
    coordinator.nvidia_torch_version = "2.1.0+cu118"
    coordinator.nvidia_torchvision_version = "0.16+cu118"
    coordinator.amd_torch_version = "2.1.0+rocm5.6"
    coordinator.amd_torchvision_version = "0.16.0+rocm5.6"
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

    assert needed == [
        "torch==2.1.0+cu118",
        "torchvision==0.16+cu118",
        "diffusers==0.27.2",
        "accelerate==0.27.2",
    ]
    assert "pip" not in needed
    assert "wheel" not in needed
    assert "PySide6" not in needed


def test_get_needed_amd_is_inference_only() -> None:
    mode_backend, get_needed = _build_get_needed(is_win=False)
    coordinator = _coordinator_stub(mode="amd")
    coordinator._mode_backend_needed = lambda mode: mode_backend(coordinator, mode)

    needed = get_needed(coordinator)

    assert needed == [
        "torch==2.1.0+rocm5.6",
        "torchvision==0.16.0+rocm5.6",
        "diffusers==0.27.2",
        "accelerate==0.27.2",
    ]
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

    assert nvidia_needed[-2:] == amd_needed[-2:] == remote_needed
    assert nvidia_needed[:-2] == ["torch==2.1.0+cu118", "torchvision==0.16+cu118"]
    assert amd_needed[:-2] == ["torch==2.1.0+rocm5.6", "torchvision==0.16.0+rocm5.6"]
