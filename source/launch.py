import datetime
import importlib.util
import os
import pathlib
import platform
import subprocess
import sys
import traceback

# Apply cache-killer flags before any Qt imports occur.
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")
os.environ.setdefault("QT_DISABLE_SHADER_DISK_CACHE", "1")
os.environ.setdefault("QSG_RHI_DISABLE_SHADER_DISK_CACHE", "1")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
EXPECTED_VENV = (REPO_ROOT / ".venv").resolve()
CRASH_LOG_PATH = REPO_ROOT / "crash.log"
LAUNCHER = REPO_ROOT / "qDiffusion.exe"
IS_WIN = platform.system() == "Windows"
ERRORED = False
REQUIRED_PYSIDE6_MODULES = (
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtNetwork",
    "PySide6.QtSql",
)

def exceptHook(exc_type, exc_value, exc_tb):
    global ERRORED
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    CRASH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CRASH_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"LAUNCH {datetime.datetime.now().isoformat()}\\n{tb}\\n")
    print(tb)
    print(f"TRACEBACK SAVED: {CRASH_LOG_PATH}")

    if IS_WIN and LAUNCHER.exists() and not ERRORED:
        ERRORED = True
        message = f"{tb}\nError saved to crash.log"
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.run([str(LAUNCHER), "-e", message], startupinfo=startupinfo)


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


def _ensure_runtime_requirements() -> None:
    if not _is_inside_expected_venv():
        raise RuntimeError("launch.py must run from .venv. Run scripts/bootstrap.py")

    missing_modules = [name for name in REQUIRED_PYSIDE6_MODULES if importlib.util.find_spec(name) is None]
    if missing_modules:
        modules = ", ".join(missing_modules)
        raise RuntimeError(
            f"PySide6 runtime modules are missing in .venv: {modules}. "
            "Run scripts/bootstrap.py to reinstall GUI dependencies."
        )

    missing_gui_modules = [name for name in REQUIRED_GUI_MODULES if importlib.util.find_spec(name) is None]
    if missing_gui_modules:
        modules = ", ".join(missing_gui_modules)
        raise RuntimeError(
            f"GUI runtime modules are missing in .venv: {modules}. "
            "Run scripts/bootstrap.py --mode gui to reinstall GUI dependencies."
        )


if __name__ == "__main__":
    sys.excepthook = exceptHook
    _ensure_runtime_requirements()

    import main

    main.main()
