import datetime
import os
import pathlib
import platform
import subprocess
import sys
import traceback
from dataclasses import dataclass
from typing import Callable

from runtime_requirements import missing_python_requirements

# Apply cache-killer flags before any Qt imports occur.
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
os.environ.setdefault("PYTHONNOUSERSITE", "1")
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")
os.environ.setdefault("QT_DISABLE_SHADER_DISK_CACHE", "1")
os.environ.setdefault("QSG_RHI_DISABLE_SHADER_DISK_CACHE", "1")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
EXPECTED_VENV = (REPO_ROOT / ".venv").resolve()
CRASH_LOG_PATH = REPO_ROOT / "crash.log"
LAUNCHER = REPO_ROOT / "qDiffusion.exe"
IS_WIN = platform.system() == "Windows"
ERRORED = False
GUI_REQUIREMENTS_PATH = REPO_ROOT / "requirements" / "gui.txt"


def _candidate_portable_qt_dirs() -> dict[str, pathlib.Path | list[pathlib.Path] | None]:
    pyside6_root = EXPECTED_VENV / "Lib" / "site-packages" / "PySide6"
    qt_bin_candidates = [pyside6_root / "Qt" / "bin", pyside6_root]
    plugin_candidates = [pyside6_root / "plugins", pyside6_root / "Qt" / "plugins"]
    qml_candidates = [pyside6_root / "qml", pyside6_root / "Qt" / "qml"]

    qt_bin_dirs = [path for path in qt_bin_candidates if path.exists()]
    plugins_dir = next((path for path in plugin_candidates if path.exists()), None)
    qml_dir = next((path for path in qml_candidates if path.exists()), None)

    return {
        "pyside6_root": pyside6_root if pyside6_root.exists() else None,
        "qt_bin_dirs": qt_bin_dirs,
        "plugins_dir": plugins_dir,
        "qml_dir": qml_dir,
    }


def _configure_portable_qt_runtime() -> None:
    dirs = _candidate_portable_qt_dirs()
    qt_bin_dirs = dirs["qt_bin_dirs"] or []
    plugins_dir = dirs["plugins_dir"]
    qml_dir = dirs["qml_dir"]

    if IS_WIN:
        for dll_dir in qt_bin_dirs:
            try:
                os.add_dll_directory(str(dll_dir))
            except (OSError, FileNotFoundError):
                continue

    if qt_bin_dirs:
        existing_path = os.environ.get("PATH", "")
        new_parts = [str(path) for path in qt_bin_dirs]
        if existing_path:
            new_parts.append(existing_path)
        os.environ["PATH"] = os.pathsep.join(new_parts)

    if plugins_dir:
        os.environ["QT_PLUGIN_PATH"] = str(plugins_dir)
        platform_plugin_dir = plugins_dir / "platforms"
        if platform_plugin_dir.exists():
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platform_plugin_dir)

    if qml_dir:
        os.environ["QML2_IMPORT_PATH"] = str(qml_dir)
        os.environ["QML_IMPORT_PATH"] = str(qml_dir)


_configure_portable_qt_runtime()


@dataclass(frozen=True)
class PreflightStage:
    name: str
    checker: Callable[[], None]
    remediation: str


def _windows_hidden_subprocess_kwargs() -> dict[str, object]:
    if not IS_WIN:
        return {}
    kwargs: dict[str, object] = {}
    startupinfo_cls = getattr(subprocess, "STARTUPINFO", None)
    startf_use_show_window = getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    if startupinfo_cls and startf_use_show_window:
        startupinfo = startupinfo_cls()
        startupinfo.dwFlags |= startf_use_show_window
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        kwargs["startupinfo"] = startupinfo
    creation_flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if creation_flag:
        kwargs["creationflags"] = creation_flag
    return kwargs

def exceptHook(exc_type, exc_value, exc_tb):
    global ERRORED
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    CRASH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CRASH_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"LAUNCH {datetime.datetime.now().isoformat()}\\n{tb}\\n")
    print(tb)
    print(f"TRACEBACK SAVED: {CRASH_LOG_PATH}")
    try:
        full_log = CRASH_LOG_PATH.read_text(encoding="utf-8")
    except Exception as log_error:
        print(f"FAILED TO READ CRASH LOG: {log_error}")
    else:
        print("----- BEGIN crash.log -----")
        print(full_log, end="" if full_log.endswith("\n") else "\n")
        print("----- END crash.log -----")

    if IS_WIN and LAUNCHER.exists() and not ERRORED:
        ERRORED = True
        message = f"{tb}\nError saved to crash.log"
        subprocess.run([str(LAUNCHER), "-e", message], **_windows_hidden_subprocess_kwargs())


def _normalized(path_value: str) -> pathlib.Path:
    return pathlib.Path(path_value).resolve()


def _is_inside_expected_venv() -> bool:
    virtual_env = os.environ.get("VIRTUAL_ENV")
    if not virtual_env:
        return False

    if _normalized(virtual_env) != EXPECTED_VENV:
        return False

    exec_path = _normalized(sys.executable)
    try:
        exec_path.relative_to(EXPECTED_VENV)
    except ValueError:
        return False

    return True


def _load_requirements(requirement_path: pathlib.Path) -> list[str]:
    requirements: list[str] = []
    with requirement_path.open(encoding="utf-8") as requirements_file:
        for line in requirements_file:
            requirement = line.split("#", 1)[0].strip()
            if requirement:
                requirements.append(requirement)
    return requirements


def _ensure_runtime_requirements() -> None:
    gui_requirements = _load_requirements(GUI_REQUIREMENTS_PATH)
    missing_gui_requirements = missing_python_requirements(gui_requirements, enforce_version=False)

    if not missing_gui_requirements:
        return

    requirements = ", ".join(missing_gui_requirements)
    raise RuntimeError(
        "GUI runtime dependencies are missing or broken for launch: "
        f"{requirements}. "
        "Run scripts/bootstrap.py manually from the repository .venv to install/repair GUI dependencies. "
        "Normal startup is validation-only and will not mutate .venv."
    )


def _log_preflight(stage: str, status: str, message: str, remediation: str | None = None) -> None:
    timestamp = datetime.datetime.now().isoformat()
    line = f"PREFLIGHT {timestamp} [{status}] {stage}: {message}"
    if remediation:
        line += f" | Remediation: {remediation}"
    CRASH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CRASH_LOG_PATH.open("a", encoding="utf-8") as crash_log:
        crash_log.write(line + "\n")


def _validate_environment_and_venv() -> None:
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise RuntimeError("PYTHONDONTWRITEBYTECODE must be set to 1 before launching.")
    if os.environ.get("PYTHONNOUSERSITE") != "1":
        raise RuntimeError("PYTHONNOUSERSITE must be set to 1 before launching.")
    if not _is_inside_expected_venv():
        raise RuntimeError("launch.py must run from .venv.")


def _validate_gui_dependencies() -> None:
    _ensure_runtime_requirements()



class _StartupLock:
    def __init__(self, lock_path: pathlib.Path) -> None:
        self._lock_path = lock_path
        self._fh = None

    def __enter__(self) -> "_StartupLock":
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self._lock_path.open("a+", encoding="utf-8")
        try:
            if IS_WIN:
                import msvcrt

                msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError(
                "Another qDiffusion launch is already running. Wait for it to finish and retry."
            ) from exc
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fh is None:
            return
        try:
            if IS_WIN:
                import msvcrt

                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None


PREFLIGHT_STAGES: tuple[PreflightStage, ...] = (
    PreflightStage(
        name="environment/venv validation",
        checker=_validate_environment_and_venv,
        remediation="Run scripts/bootstrap.py and launch from the repository .venv with PYTHONNOUSERSITE=1.",
    ),
    PreflightStage(
        name="GUI dependency validation",
        checker=_validate_gui_dependencies,
        remediation="Run scripts/bootstrap.py manually from the repository .venv to install/repair GUI dependencies.",
    ),
)


def run_preflight_pipeline() -> None:
    with _StartupLock(REPO_ROOT / ".tmp" / "launch.lock"):
        for stage in PREFLIGHT_STAGES:
            _log_preflight(stage.name, "START", "stage started", remediation=stage.remediation)
            try:
                stage.checker()
            except Exception as exc:
                _log_preflight(stage.name, "FAIL", str(exc), remediation=stage.remediation)
                raise RuntimeError(f"Preflight stage failed: {stage.name}. {exc}") from exc
            _log_preflight(stage.name, "OK", "stage completed", remediation=stage.remediation)


if __name__ == "__main__":
    sys.excepthook = exceptHook
    run_preflight_pipeline()

    import main

    main.main()
