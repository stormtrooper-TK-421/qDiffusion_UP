# AGENTS.md — qDiffusion_UP repo working agreement

This file defines repository-specific operating rules for contributors and coding agents.

## Python environment and isolation
- **No system python contamination.** Always run commands through this repository's virtual environment, never through system/global Python.
- Always set `PYTHONNOUSERSITE=1` for Python tooling and runtime commands.
- **Single-venv design is mandatory:**
  - `.venv` for GUI + inference dependencies.
  - `.tmp` for disposable runtime/cache artifacts.
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
- **ONLY cloning allowed is via `scripts/fetch_sd_infer.py` into `source/sd-inference-server/`.**
- Treat `source/sd-inference-server/` as read-only external code; do not edit it in port tickets.

## QML loading policy (PySide6 port target)
- Once the PySide6 port is complete, QML must load from `qrc:/` paths.
- `file:` QML loading paths are not allowed in that final state.
