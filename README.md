## Qt GUI for Stable diffusion
--------
Built from the ground up alongside [sd-inference-server](https://github.com/stormtrooper-TK-421/sd-inference-server), the backend for this GUI.
![example](https://github.com/stormtrooper-TK-421/qDiffusion_UP/raw/master/source/screenshot.png)
\*new\* Discord: [Arena Systems](https://discord.gg/WdjKqUGefU).

## Getting started
### Install
1. [Download](https://github.com/stormtrooper-TK-421/qDiffusion_UP/archive/refs/heads/master.zip) this repo as a zip and extract it.
2. Run `qDiffusion.exe` (or `bash ./source/start.sh` on Linux, `sh ./source/start-mac.sh` on Mac).
	- First time users will need to wait for the managed Python runtime (minimum `3.14.3`) and PySide6 to be downloaded.
	- AMD Ubuntu users need to follow: [Install ROCm](https://github.com/stormtrooper-TK-421/qDiffusion_UP/wiki/Install#ubuntu-22).
3. Select a mode. `Remote`, `Nvidia` and `AMD` are available.
	- `Remote` needs `~500MB` of space, `NVIDIA`/`AMD` need `~5-10GB`.
	- Choose `Remote` if you only want to generate using cloud/server instances.
	- For local generation choose `NVIDIA` or `AMD`, they also have the capabilities of `Remote`.
	- `AMD` on Windows uses DirectML so is much slower than on Linux.
4. Press Install. Requirements will be downloaded.
	- Output is displayed on screen, fatal errors are written to `crash.log`.
5. Done. NOTE: Update using `File->Update` or `Settings->Program->Update`.

Information is available on the [Wiki](https://github.com/stormtrooper-TK-421/qDiffusion_UP/wiki/Guide).

### Python requirement files
- `requirements/gui.txt` = mandatory for launch + installer UI.
- `requirements/inference-server.txt` = canonical optional inference dependencies for installer planning.

### Dependency phase split contract (developers)
- **Phase A (bootstrap/launch):** only `requirements/gui.txt` is allowed.
  - Allowed examples: `PySide6`, `Pillow`, `websockets`, `pygit2`.
  - Forbidden examples in phase A: `diffusers`, `transformers`, `accelerate`, `k_diffusion`, `segment-anything`, `timm`, `ultralytics`.
- **Phase B (installer/inference planning):** only `requirements/inference-server.txt` is allowed.
  - Installer planning code must read `requirements/inference-server.txt` and must not read legacy inference sources.
  - Forbidden references in planner code: `source/sd-inference-server/requirements.txt`.
- Enforcement: run `scripts/check_dependency_phase_split.py` (also run by `scripts/prebuild_check.py`).

See `docs/dependency_phase_contract.md` for the full developer contract.

### Bootstrap scope
- `scripts/bootstrap.py` is only for startup/GUI readiness.
- It creates or repairs `.venv` and installs `requirements/gui.txt`.
- It does **not** install backend model or inference dependency sets.


### Remote
Notebooks for running a remote instance are available: [Colab](https://colab.research.google.com/github/stormtrooper-TK-421/qDiffusion_UP/blob/master/remote_colab.ipynb), [Kaggle](https://www.kaggle.com/code/arenasys/qdiffusion), [SageMaker](https://studiolab.sagemaker.aws/import/github/stormtrooper-TK-421/qDiffusion_UP/blob/master/remote_sagemaker.ipynb)

0. [Install](#install) qDiffusion, this runs locally on your machine and connects to the backend server.
	- If using Mobile then skip this step.
1. Open the [Colab](https://colab.research.google.com/github/stormtrooper-TK-421/qDiffusion_UP/blob/master/remote_colab.ipynb) notebook. Requires a Google account.
2. Press the play button in the top left. Colab may take some time to configure a machine for you.
3. Accept or reject the Google Drive permission popup.
	- Accepting will mean models are saved/loaded from `qDiffusion/models` on your drive.
	- Rejecting will mean models are local, you will need to download them again next time.
4. Wait for the requirements to be downloaded and the server to start (scroll down).
5. Click the `DESKTOP` link to start qDiffusion and/or connect.
   	- Alternatively copy the Endpoint and Password to qDiffusion under `Settings->Remote`, press Connect.
6. Done. See [Downloads](https://github.com/stormtrooper-TK-421/qDiffusion_UP/wiki/Guide#downloading) for how to get models onto the instance.
	- Remaking the instance is done via `Runtime->Disconnect and delete runtime`, then close the tab and start from Step 1.
	- HTTP 530 means the cloudflare tunnel is not working. Wait for an update, or check [Here](https://www.cloudflarestatus.com/).
	- Runtime disconnects due to "disallowed code" can happen occasionally, often when merging. For now these don't appear to be targeted at qDiffusion specifically.

### Mobile
[qDiffusion Web](https://github.com/arenasys/arenasys.github.io) is available for mobile users. Features are limited compared to the full GUI (txt2img only).

### Overview
- Stable diffusion 1.x, 2.x (including v-prediction), XL (only Base)
- Txt2Img, Img2Img, Inpainting, HR Fix and Upscaling modes
- Prompt and network weighting and scheduling
- Hypernetworks
- LoRAs (including LoCon)
- Textual inversion Embeddings
- Model pruning and conversion
- Subprompts via Composable Diffusion
- Live preview modes
- Optimized attention
- Minimal VRAM mode
- Device selection
- ControlNet
- Merging
- ~~LoRA Training~~ (working on it!)
