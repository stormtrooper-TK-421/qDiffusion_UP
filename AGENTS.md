# AGENTS.md — qDiffusion_UP repo working agreement

This file defines repository-specific operating rules for contributors and coding agents.

## Python environment and isolation
- **No system python contamination.** Always run commands through this repository's virtual environments, never through system/global Python.
- Always set `PYTHONNOUSERSITE=1` for Python tooling and runtime commands.
- **Two-venv design is mandatory:**
  - `.venv_gui` for the PySide6 GUI toolchain.
  - `.venv_infer` for torch/diffusers/inference dependencies.
- Do not mix dependencies across those environments.
- Forbid execution against global site-packages.

## Cache and bytecode policy
- **No code caches.** Always set `PYTHONDONTWRITEBYTECODE=1`.
- `__pycache__` directories must be removed during clean steps.

## Qt/QML cache policy
- **No Qt disk caches.** Always set all of:
  - `QML_DISABLE_DISK_CACHE=1`
  - `QT_DISABLE_SHADER_DISK_CACHE=1`
  - `QSG_RHI_DISABLE_SHADER_DISK_CACHE=1`

## Inference server source policy
- **No runtime git clones.** The inference server must be present in-repo via vendoring or submodule.
- Do not clone inference dependencies at application launch/runtime.

## QML loading policy (PySide6 port target)
- Once the PySide6 port is complete, QML must load from `qrc:/` paths.
- `file:` QML loading paths are not allowed in that final state.
