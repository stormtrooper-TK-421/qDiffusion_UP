# Dependency phase split contract (developer)

This repository enforces a strict two-phase dependency model.

## Phase A — bootstrap + launch (pre-installer)

**Purpose:** make the app launch and show installer UI only.

**Canonical source:** `requirements/gui.txt`

### Allowed in Phase A
- Reading/installing `requirements/gui.txt` in bootstrap/launch code.
- GUI/runtime essentials needed before installer interaction.
- All startup entrypoints (`qDiffusion.exe`, `source/start.bat`, `source/start.sh`, `source/start-mac.sh`) must run `scripts/bootstrap.py` before `source/launch.py`.

Concrete examples (allowed in `requirements/gui.txt`):
- `PySide6`
- `Pillow`
- `websockets`
- `pygit2`

### Not allowed in Phase A
- Importing inference dependency sources.
- Carrying inference-only libraries in GUI requirements.

Concrete examples (forbidden in `requirements/gui.txt`):
- `diffusers`
- `transformers`
- `accelerate`
- `k_diffusion`
- `segment-anything`
- `timm`
- `ultralytics`

## Phase B — installer planning + inference features

**Purpose:** optional/model stack dependencies selected by install mode.

**Canonical source:** `requirements/inference-server.txt`

### Allowed in Phase B
- Installer planning logic loads inference requirements from `requirements/inference-server.txt`.
- Inference-only packages are defined in this canonical file.

### Not allowed in Phase B
- Using legacy or alternate inference source files in planning logic.

Concrete examples (forbidden references):
- `source/sd-inference-server/requirements.txt` (planner should use synced canonical file instead)

## Enforcement

Use `scripts/check_dependency_phase_split.py` directly or through `scripts/prebuild_check.py`.
