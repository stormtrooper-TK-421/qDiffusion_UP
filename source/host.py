import os
import sys
import traceback
import multiprocessing
import datetime
import time
import random
import string
import subprocess
from pathlib import Path

from PySide6.QtCore import Slot as pyqtSlot, Signal as pyqtSignal

import remote


REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = REPO_ROOT / ".venv"
INFER_SERVER = REPO_ROOT / "source" / "sd-inference-server" / "server.py"


def get_inference_server_path():
    infer_path = INFER_SERVER.parent
    if not infer_path.is_dir() or not INFER_SERVER.is_file():
        raise FileNotFoundError(
            "Missing vendored inference server at source/sd-inference-server. "
            "Fetch it with `python scripts/fetch_sd_infer.py`."
        )
    return infer_path


def log_traceback(label):
    exc_type, exc_value, exc_tb = sys.exc_info()
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    with open("crash.log", "a", encoding='utf-8') as f:
        f.write(f"{label} {datetime.datetime.now()}\n{tb}\n")
    print(label, tb)
    return tb


def _venv_python() -> Path:
    python_bin = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / "python"
    if not python_bin.is_file():
        raise RuntimeError(f"Missing .venv python interpreter: {python_bin}")
    return python_bin


def _build_env() -> dict[str, str]:
    clean_env: dict[str, str] = {}
    for key, value in os.environ.items():
        upper = key.upper()
        if upper.startswith(("QT_", "QML_", "PYTHON", "PIP")):
            continue
        clean_env[key] = value

    clean_env.update(
        {
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PIP_NO_CACHE_DIR": "1",
            "QML_DISABLE_DISK_CACHE": "1",
            "QT_DISABLE_SHADER_DISK_CACHE": "1",
            "QSG_RHI_DISABLE_SHADER_DISK_CACHE": "1",
            "VIRTUAL_ENV": str(VENV_DIR),
        }
    )

    venv_bin = str(_venv_python().parent)
    inherited_path = clean_env.get("PATH", "")
    clean_env["PATH"] = os.pathsep.join([venv_bin, inherited_path]) if inherited_path else venv_bin
    return clean_env


class HostProcess(multiprocessing.Process):
    def __init__(self, ip, port, password, tunnel, read_only, monitor, model_directory, loaded, stop, response):
        super().__init__()
        self.ip = ip
        self.port = port
        self.tunnel = tunnel
        self.read_only = read_only
        self.monitor = monitor
        self.password = password
        self.model_directory = Path(model_directory).resolve()

        self.loaded = loaded
        self.stop = stop
        self.response = response

        self.server_proc = None
        self.tunnel_manager = None

    def _stop_server(self):
        if self.server_proc and self.server_proc.poll() is None:
            self.server_proc.terminate()
            try:
                self.server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_proc.kill()
                self.server_proc.wait(timeout=5)

    def _stop_tunnel(self):
        if self.tunnel_manager:
            try:
                self.tunnel_manager.terminate(self.port)
            except Exception:
                pass
            self.tunnel_manager = None

    def run(self):
        if sys.stdout is None:
            sys.stdout = open(os.devnull, 'w')
            sys.__stdout__ = sys.stdout
        if sys.stderr is None:
            sys.stderr = open(os.devnull, 'w')
            sys.__stderr__ = sys.stderr

        try:
            get_inference_server_path()
            self.model_directory.mkdir(parents=True, exist_ok=True)
            env = _build_env()
            python_bin = _venv_python()

            cmd = [
                str(python_bin),
                str(INFER_SERVER),
                "--bind",
                f"{self.ip}:{self.port}",
                "--models",
                str(self.model_directory),
                "--password",
                self.password,
                "--owner",
            ]
            if self.read_only:
                cmd.append("--read-only")
            if self.monitor:
                cmd.append("--monitor")

            self.server_proc = subprocess.Popen(
                cmd,
                cwd=str(REPO_ROOT),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )

            endpoint = f"ws://{self.ip}:{self.port}"
            if self.tunnel:
                from pycloudflared import try_cloudflare
                self.tunnel_manager = try_cloudflare
                tunnel_url = try_cloudflare(port=self.port, verbose=False)
                endpoint = tunnel_url.tunnel.replace("https", "wss")

            self.response.put({"type": "host", "data": {"endpoint": endpoint, "password": self.password}})
            self.loaded.set()

            while True:
                if self.stop.is_set():
                    break
                if self.server_proc.poll() is not None:
                    raise RuntimeError("Host inference server exited unexpectedly")
                time.sleep(0.5)
        except Exception as e:
            log_traceback("LOCAL HOST")
            self.response.put({"type": "remote_error", "data": {"message": str(e)}})
        finally:
            self._stop_tunnel()
            self._stop_server()


class HostInference(remote.RemoteInference):
    response = pyqtSignal(object)

    def __init__(self, gui, ip, port, password, tunnel, read_only, monitor):
        endpoint = f"ws://{ip}:{port}"
        if not password:
            password = ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(8))

        super().__init__(gui, endpoint, password)

        self.loaded_sig = multiprocessing.Event()
        self.stop_sig = multiprocessing.Event()

        self.host_response = multiprocessing.Queue(16)
        self.host = HostProcess(ip, port, password, tunnel, read_only, monitor, self.gui.modelDirectory(), self.loaded_sig, self.stop_sig, self.host_response)

    def run(self):
        self.onResponse({"type": "status", "data": {"message": "Initializing"}})
        self.host.start()

        for _ in range(10):
            self.loaded_sig.wait(1)
            if self.loaded_sig.is_set() or not self.host_response.empty():
                break

        if not self.loaded_sig.is_set():
            self.stop_sig.set()
            error = {"type": "remote_error", "data": {"message": "Timeout starting host"}}
            if not self.host_response.empty():
                error = self.host_response.get_nowait()
            self.onResponse(error)
            return

        while not self.host_response.empty():
            self.onResponse(self.host_response.get_nowait())

        time.sleep(0.5)

        super().run()

    @pyqtSlot()
    def stop(self):
        self.stop_sig.set()
        if self.host.is_alive():
            self.host.join(timeout=5)
            if self.host.is_alive():
                self.host.terminate()
        super().stop()
