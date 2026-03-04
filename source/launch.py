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
QML_ROOT = REPO_ROOT / "source" / "qml"
QML_RC_PATH = QML_ROOT / "qml_rc.py"
QML_QRC_PATH = QML_ROOT / "qml.qrc"
INFERENCE_SOURCE_TREE = REPO_ROOT / "source" / "sd-inference-server"
SYNC_INFER_REQUIREMENTS_SCRIPT = REPO_ROOT / "scripts" / "sync_infer_requirements.py"


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
    missing_gui_requirements = missing_python_requirements(gui_requirements, enforce_version=True)

    if not missing_gui_requirements:
        return

    bootstrap_command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "bootstrap.py"),
    ]
    bootstrap_result = subprocess.run(
        bootstrap_command,
        capture_output=True,
        text=True,
        check=False,
        **_windows_hidden_subprocess_kwargs(),
    )
    if bootstrap_result.returncode != 0:
        requirements = ", ".join(missing_gui_requirements)
        bootstrap_stdout = (bootstrap_result.stdout or "(no stdout)").strip()
        bootstrap_stderr = (bootstrap_result.stderr or "(no stderr)").strip()
        compatibility_report = _extract_compatibility_probe_report(bootstrap_stdout, bootstrap_stderr)
        compatibility_details = ""
        if compatibility_report:
            compatibility_details = f" Compatibility probe details: {compatibility_report}."
        raise RuntimeError(
            "Failed to bootstrap GUI dependencies. "
            f"Missing requirements before bootstrap: {requirements}. "
            f"{compatibility_details}"
            f"bootstrap stdout: {bootstrap_stdout} | bootstrap stderr: {bootstrap_stderr}"
        )

    missing_gui_requirements = missing_python_requirements(gui_requirements, enforce_version=True)
    if missing_gui_requirements:
        requirements = ", ".join(missing_gui_requirements)
        raise RuntimeError(
            "GUI runtime requirements are still missing after bootstrap: "
            f"{requirements}. Run scripts/bootstrap.py to reinstall GUI dependencies."
        )


def _extract_compatibility_probe_report(stdout: str, stderr: str) -> str:
    marker = "COMPATIBILITY PROBE FAILED"
    for source in (stdout, stderr):
        lines = [line.strip() for line in source.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            if marker not in line:
                continue
            return " ; ".join(lines[index:])
    return ""


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


def _validate_or_repair_gui_dependencies() -> None:
    _ensure_runtime_requirements()


def _build_qml_qrc() -> None:
    import glob
    import shutil

    if QML_QRC_PATH.exists():
        QML_QRC_PATH.unlink()

    items: list[pathlib.Path] = []
    for tab_path in (REPO_ROOT / "source" / "tabs").glob("*"):
        for src in tab_path.glob("*.*"):
            if src.suffix.lower() not in {".qml", ".svg"}:
                continue
            dst = QML_ROOT / src.relative_to(REPO_ROOT / "source")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst)
            items.append(dst)

    for pattern in ("*.qml", "components/*.qml", "style/*.qml", "fonts/*.ttf", "icons/*.svg"):
        items.extend(pathlib.Path(path) for path in glob.glob(str(QML_ROOT / pattern)))

    qrc_entries = []
    for item in sorted({path.resolve() for path in items}):
        relative_item = item.relative_to(QML_ROOT).as_posix()
        qrc_entries.append(f"\t\t<file>{relative_item}</file>\n")

    contents = f"""<RCC>\n\t<qresource prefix=\"/\">\n{''.join(qrc_entries)}\t</qresource>\n</RCC>"""
    QML_QRC_PATH.write_text(contents, encoding="utf-8")


def _compile_qml_resources() -> None:
    qml_rc_module = QML_ROOT / "qml_rc.py"
    if qml_rc_module.exists():
        qml_rc_module.unlink()

    status = subprocess.run(
        ["pyside6-rcc", "-o", str(qml_rc_module), str(QML_QRC_PATH)],
        capture_output=True,
        text=True,
        check=False,
        **_windows_hidden_subprocess_kwargs(),
    )
    if status.returncode != 0:
        details = (
            f"stdout: {(status.stdout or '(no stdout)').strip()} | "
            f"stderr: {(status.stderr or '(no stderr)').strip()}"
        )
        raise RuntimeError(f"pyside6-rcc failed to compile QML resources: {details}")

    tabs_copy = QML_ROOT / "tabs"
    if tabs_copy.exists():
        import shutil

        shutil.rmtree(tabs_copy, ignore_errors=True)
    if QML_QRC_PATH.exists():
        QML_QRC_PATH.unlink()


def _ensure_qml_resources_ready() -> None:
    if QML_RC_PATH.exists():
        return
    _build_qml_qrc()
    _compile_qml_resources()


def _validate_inference_source_tree() -> None:
    if INFERENCE_SOURCE_TREE.is_dir():
        return
    raise RuntimeError(
        f"Missing inference source tree at {INFERENCE_SOURCE_TREE}."
    )


def _sync_inference_requirements() -> None:
    status = subprocess.run(
        [sys.executable, str(SYNC_INFER_REQUIREMENTS_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        **_windows_hidden_subprocess_kwargs(),
    )
    if status.returncode != 0:
        details = (
            f"stdout: {(status.stdout or '(no stdout)').strip()} | "
            f"stderr: {(status.stderr or '(no stderr)').strip()}"
        )
        raise RuntimeError(f"Failed to sync inference requirements: {details}")


PREFLIGHT_STAGES: tuple[PreflightStage, ...] = (
    PreflightStage(
        name="environment/venv validation",
        checker=_validate_environment_and_venv,
        remediation="Run scripts/bootstrap.py and launch from the repository .venv with PYTHONNOUSERSITE=1.",
    ),
    PreflightStage(
        name="GUI dependency validation + repair",
        checker=_validate_or_repair_gui_dependencies,
        remediation="Run scripts/bootstrap.py to reinstall GUI dependencies.",
    ),
    PreflightStage(
        name="QML resource readiness",
        checker=_ensure_qml_resources_ready,
        remediation="Ensure pyside6-rcc is available in .venv and rerun launch.py.",
    ),
    PreflightStage(
        name="inference source tree presence",
        checker=_validate_inference_source_tree,
        remediation="Restore source/sd-inference-server (for example, initialize vendored inference sources).",
    ),
    PreflightStage(
        name="inference requirements sync",
        checker=_sync_inference_requirements,
        remediation="Run scripts/sync_infer_requirements.py after restoring source/sd-inference-server.",
    ),
)


def run_preflight_pipeline() -> None:
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
