import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

from PySide6.QtCore import Slot as pyqtSlot, Signal as pyqtSignal

import remote


REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = REPO_ROOT / ".venv"
TMP_ROOT = REPO_ROOT / ".tmp"
FETCH_SCRIPT = REPO_ROOT / "scripts" / "fetch_sd_infer.py"
INFER_SERVER = REPO_ROOT / ".third_party" / "sd-inference-server" / "server.py"
LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 28888


class LocalInference(remote.RemoteInference):
    response = pyqtSignal(object)

    def __init__(self, gui):
        endpoint = f"ws://{LOCAL_HOST}:{LOCAL_PORT}"
        super().__init__(gui, endpoint, remote.DEFAULT_PASSWORD)
        self.server_proc = None
        self._server_logs = []
        self._log_thread = None

    def _venv_python(self) -> Path:
        python_bin = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / "python"
        if not python_bin.is_file():
            raise RuntimeError(f"Missing .venv python interpreter: {python_bin}")
        return python_bin

    def _build_env(self) -> dict[str, str]:
        clean_env = {}
        for key, value in os.environ.items():
            upper = key.upper()
            if upper.startswith(("QT_", "QML_", "PYTHON", "PIP")):
                continue
            clean_env[key] = value

        xdg_cache = TMP_ROOT / "xdg_cache"
        xdg_config = TMP_ROOT / "xdg_config"
        xdg_data = TMP_ROOT / "xdg_data"
        xdg_state = TMP_ROOT / "xdg_state"
        self._reset_tmp_root()
        for path in (TMP_ROOT, xdg_cache, xdg_config, xdg_data, xdg_state):
            path.mkdir(parents=True, exist_ok=True)

        clean_env.update(
            {
                "TMPDIR": str(TMP_ROOT),
                "TEMP": str(TMP_ROOT),
                "TMP": str(TMP_ROOT),
                "XDG_CACHE_HOME": str(xdg_cache),
                "XDG_CONFIG_HOME": str(xdg_config),
                "XDG_DATA_HOME": str(xdg_data),
                "XDG_STATE_HOME": str(xdg_state),
                "PYTHONNOUSERSITE": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PIP_NO_CACHE_DIR": "1",
                "QML_DISABLE_DISK_CACHE": "1",
                "QT_DISABLE_SHADER_DISK_CACHE": "1",
                "QSG_RHI_DISABLE_SHADER_DISK_CACHE": "1",
                "VIRTUAL_ENV": str(VENV_DIR),
            }
        )

        venv_bin = str(self._venv_python().parent)
        inherited_path = clean_env.get("PATH", "")
        clean_env["PATH"] = os.pathsep.join([venv_bin, inherited_path]) if inherited_path else venv_bin
        return clean_env

    def _reset_tmp_root(self) -> None:
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def _read_server_logs(self):
        if not self.server_proc or not self.server_proc.stdout:
            return
        for line in self.server_proc.stdout:
            if not line:
                continue
            self._server_logs.append(line.rstrip())
            if len(self._server_logs) > 100:
                self._server_logs.pop(0)

    def _run_fetch(self, env: dict[str, str], python_bin: Path) -> None:
        self.onResponse({"type": "status", "data": {"message": "Preparing local server"}})
        result = subprocess.run(
            [str(python_bin), str(FETCH_SCRIPT)],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stdout.strip() or "fetch_sd_infer.py failed")
        if not INFER_SERVER.is_file():
            raise RuntimeError(f"Missing local inference server entrypoint: {INFER_SERVER}")

    def _wait_until_listening(self, timeout_s: float = 30.0) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline and not self.stopping:
            if self.server_proc and self.server_proc.poll() is not None:
                raise RuntimeError("Local server exited during startup")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                if sock.connect_ex((LOCAL_HOST, LOCAL_PORT)) == 0:
                    return
            time.sleep(0.2)
        raise RuntimeError("Timed out waiting for local server")

    def _spawn_server(self, env: dict[str, str], python_bin: Path) -> None:
        self.onResponse({"type": "status", "data": {"message": "Starting local server"}})
        self.server_proc = subprocess.Popen(
            [
                str(python_bin),
                str(INFER_SERVER),
                "--host",
                LOCAL_HOST,
                "--port",
                str(LOCAL_PORT),
            ],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self._log_thread = threading.Thread(target=self._read_server_logs, daemon=True)
        self._log_thread.start()
        self._wait_until_listening()

    def run(self):
        try:
            python_bin = self._venv_python()
            env = self._build_env()
            self._run_fetch(env, python_bin)
            self._spawn_server(env, python_bin)
        except Exception as exc:
            details = "\n".join(self._server_logs[-10:])
            message = str(exc)
            if details:
                message = f"{message}\n{details}"
            self.onResponse({"type": "remote_error", "data": {"message": message}})
            return

        super().run()

    @pyqtSlot()
    def stop(self):
        super().stop()
        if self.server_proc and self.server_proc.poll() is None:
            self.server_proc.terminate()
            try:
                self.server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_proc.kill()
                self.server_proc.wait(timeout=5)
        self._reset_tmp_root()
