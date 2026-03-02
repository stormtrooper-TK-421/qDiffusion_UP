import datetime
import importlib.util
import os
import pathlib
import sys
import traceback

# Apply cache-killer flags before any Qt imports occur.
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")
os.environ.setdefault("QT_DISABLE_SHADER_DISK_CACHE", "1")
os.environ.setdefault("QSG_RHI_DISABLE_SHADER_DISK_CACHE", "1")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
EXPECTED_VENV = (REPO_ROOT / ".venv").resolve()
CRASH_LOG_PATH = REPO_ROOT / ".logs" / "crash.log"
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
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    CRASH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CRASH_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"LAUNCH {datetime.datetime.now().isoformat()}\\n{tb}\\n")
    print(tb)
    print(f"TRACEBACK SAVED: {CRASH_LOG_PATH}")


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
        print("ERROR: launch.py must run from .venv. Run scripts/bootstrap.py")
        raise SystemExit(1)

    missing_modules = [name for name in REQUIRED_PYSIDE6_MODULES if importlib.util.find_spec(name) is None]
    if missing_modules:
        modules = ", ".join(missing_modules)
        print("ERROR: PySide6 runtime modules are missing in .venv:", modules)
        print("Run scripts/bootstrap.py to reinstall GUI dependencies.")
        raise SystemExit(1)


if __name__ == "__main__":
    sys.excepthook = exceptHook
    _ensure_runtime_requirements()

    import main

    main.main()
