#!/usr/bin/env python3
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "source"
QML_DIR = SOURCE_DIR / "qml"

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONNOUSERSITE", "1")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")
os.environ.setdefault("QT_DISABLE_SHADER_DISK_CACHE", "1")
os.environ.setdefault("QSG_RHI_DISABLE_SHADER_DISK_CACHE", "1")

if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonType
from PySide6.QtWidgets import QApplication


class _TranslatorInstance(QObject):
    @Slot(str, str, result=str)
    def translate(self, text: str, _file: str) -> str:
        return text


class _Translator(QObject):
    updated = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._instance = _TranslatorInstance(self)

    @Property(QObject, notify=updated)
    def instance(self) -> QObject:
        return self._instance


class _Coordinator(QObject):
    show = Signal()
    proceed = Signal()
    cancel = Signal()

    @Slot()
    def load(self) -> None:
        return


def _ensure_qrc_module() -> None:
    qml_rc_py = QML_DIR / "qml_rc.py"
    if qml_rc_py.exists():
        return

    qml_rc = QML_DIR / "qml.qrc"
    tab_files: list[str] = []
    for tab in glob.glob(str(SOURCE_DIR / "tabs" / "*")):
        for src in glob.glob(os.path.join(tab, "*.*")):
            if src.split(".")[-1] in {"qml", "svg"}:
                dst = QML_DIR / Path(src).relative_to(SOURCE_DIR)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src, dst)
                tab_files.append(str(dst))

    items = tab_files
    items += glob.glob(str(QML_DIR / "*.qml"))
    items += glob.glob(str(QML_DIR / "components" / "*.qml"))
    items += glob.glob(str(QML_DIR / "style" / "*.qml"))
    items += glob.glob(str(QML_DIR / "fonts" / "*.ttf"))
    items += glob.glob(str(QML_DIR / "icons" / "*.svg"))

    normalized = sorted({Path(item).as_posix() for item in items})
    files = "".join(f"\t\t<file>{Path(f).relative_to(QML_DIR).as_posix()}</file>\n" for f in normalized)
    qml_rc.write_text(f"<RCC>\n\t<qresource prefix=\"/\">\n{files}\t</qresource>\n</RCC>", encoding="utf-8")

    subprocess.run(["pyside6-rcc", "-o", str(qml_rc_py), str(qml_rc)], cwd=REPO_ROOT, check=True)
    shutil.rmtree(QML_DIR / "tabs", ignore_errors=True)
    qml_rc.unlink(missing_ok=True)


def main() -> int:
    _ensure_qrc_module()

    import qml.qml_rc  # noqa: F401
    import misc

    app = QApplication(["qml_smoke_test", "--no-effects"])
    engine = QQmlApplicationEngine()

    runtime_warnings: list[str] = []

    def _record_warnings(warnings: list[object]) -> None:
        runtime_warnings.extend(str(w) for w in warnings)

    engine.warnings.connect(_record_warnings)

    translator = _Translator(app)
    coordinator = _Coordinator(app)

    qmlRegisterSingletonType(_Translator, "gui", 1, 0, "TRANSLATOR", lambda _engine: translator)
    qmlRegisterSingletonType(QUrl("qrc:/Common.qml"), "gui", 1, 0, "COMMON")
    qmlRegisterSingletonType(_Coordinator, "gui", 1, 0, "COORDINATOR", lambda _engine: coordinator)
    misc.registerTypes()

    engine.load(QUrl("qrc:/Splash.qml"))
    app.processEvents()

    if not engine.rootObjects():
        raise AssertionError("Splash.qml failed to load: engine.rootObjects() is empty")

    import_failures = [w for w in runtime_warnings if any(t in w.lower() for t in ("module", "import", "not installed"))]
    if import_failures:
        raise AssertionError("Runtime QML import errors:\n" + "\n".join(import_failures))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
