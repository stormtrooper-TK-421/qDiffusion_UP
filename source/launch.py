import sys
import subprocess
import os
import platform
import traceback
import datetime
import importlib.util

VENV_DIR = os.path.join(os.getcwd(), "venv")
IS_WIN = platform.system() == "Windows"
PYTHON_RUN = sys.executable

QT_VER = "5.15.11"
QT_REQ = f"PyQt5=={QT_VER}"


def venv_python(console=True):
    if IS_WIN:
        exe = "python.exe" if console else "pythonw.exe"
        return os.path.join(VENV_DIR, "Scripts", exe)
    return os.path.join(VENV_DIR, "bin", "python")


def get_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("QT") and not k.startswith("PIP") and not k.startswith("PYTHON")}
    env["VIRTUAL_ENV"] = VENV_DIR
    env["PIP_CACHE_DIR"] = os.path.join(VENV_DIR, "cache")
    env["PIP_CONFIG_FILE"] = os.devnull
    if IS_WIN:
        env["PATH"] = os.path.join(VENV_DIR, "Scripts") + ";" + env["PATH"]
    else:
        env["PATH"] = os.path.join(VENV_DIR, "bin") + ":" + env["PATH"]

    if not IS_WIN and "HSA_OVERRIDE_GFX_VERSION" not in env:
        env["HSA_OVERRIDE_GFX_VERSION"] = "10.3.0"
    if not IS_WIN and "MIOPEN_LOG_LEVEL" not in env:
        env["MIOPEN_LOG_LEVEL"] = "4"
    return env


def restart():
    target = [venv_python(console=not IS_WIN), os.path.join("source", "launch.py")] + sys.argv[1:]
    if IS_WIN:
        subprocess.Popen(target, env=get_env(), creationflags=0x00000008 | 0x00000200)
    else:
        subprocess.Popen(target, env=get_env())
    raise SystemExit


def install_venv():
    print(f"CREATING VENV... ({VENV_DIR})")
    subprocess.run([PYTHON_RUN, "-m", "venv", VENV_DIR], check=True)


def install_qt():
    print(f"INSTALLING {QT_REQ}...")
    subprocess.run([venv_python(console=True), "-m", "pip", "install", "-U", QT_REQ], env=get_env(), check=True)


def get_qt_version():
    python = venv_python(console=True)
    if not os.path.exists(python):
        return None
    proc = subprocess.run(
        [python, "-c", "import importlib.metadata as m; print(m.version('PyQt5'), end='')"],
        capture_output=True,
        text=True,
        env=get_env(),
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def exceptHook(exc_type, exc_value, exc_tb):
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    with open("crash.log", "a", encoding="utf-8") as f:
        f.write(f"LAUNCH {datetime.datetime.now()}\n{tb}\n")
    print(tb)
    print("TRACEBACK SAVED: crash.log")

    if "pythonw" not in PYTHON_RUN:
        input("PRESS ENTER TO CLOSE")


if __name__ == "__main__":
    sys.excepthook = exceptHook

    if sys.version_info[0] < 3 or sys.version_info[1] < 10:
        print(f"Python 3.10 or greater is required. Have Python {sys.version_info[0]}.{sys.version_info[1]}.")
        input()
        raise SystemExit
    if not importlib.util.find_spec("pip"):
        print("PIP module is required.")
        input()
        raise SystemExit
    if not importlib.util.find_spec("venv"):
        print("VENV module is required.")
        input()
        raise SystemExit

    VENV_DIR = os.path.abspath(VENV_DIR)

    invalid = "".join([c for c in VENV_DIR if ord(c) > 127])
    if invalid:
        print(f"PATH INVALID ({VENV_DIR}) CONTAINS UNICODE ({invalid})")
        if IS_WIN:
            VENV_DIR = os.getcwd()[0] + ":\\qDiffusion"
            print(f"USING {VENV_DIR} INSTEAD")
        else:
            print("FAILED")
            input()
            raise SystemExit

    inside_venv = VENV_DIR in sys.executable and VENV_DIR in os.environ.get("PATH", "") and VENV_DIR == os.environ.get("VIRTUAL_ENV", "")
    missing_venv = not os.path.exists(VENV_DIR)

    if missing_venv:
        install_venv()

    if get_qt_version() != QT_VER:
        install_qt()
        if not inside_venv:
            print("DONE.")
        restart()

    if not inside_venv:
        if missing_venv:
            print("DONE.")
        restart()

    import main
    main.main()
