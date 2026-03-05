#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "source"
QML_DIR = SOURCE_DIR / "qml"
TAB_DIR = SOURCE_DIR / "tabs"

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


def _file_url(path: Path) -> str:
    return QUrl.fromLocalFile(str(path.resolve())).toString()


def main() -> int:
    import misc

    app = QApplication(["qml_smoke_test", "--no-effects"])
    engine = QQmlApplicationEngine()

    runtime_warnings: list[str] = []

    def _record_warnings(warnings: list[object]) -> None:
        runtime_warnings.extend(str(w) for w in warnings)

    engine.warnings.connect(_record_warnings)

    app_qml_root_url = _file_url(QML_DIR)
    app_tabs_root_url = _file_url(TAB_DIR)

    translator = _Translator(app)
    coordinator = _Coordinator(app)

    qmlRegisterSingletonType(_Translator, "gui", 1, 0, "TRANSLATOR", lambda _engine: translator)
    qmlRegisterSingletonType(QUrl.fromLocalFile(str((QML_DIR / "Common.qml").resolve())), "gui", 1, 0, "COMMON")
    qmlRegisterSingletonType(_Coordinator, "gui", 1, 0, "COORDINATOR", lambda _engine: coordinator)
    misc.registerTypes()

    engine.rootContext().setContextProperty("APP_QML_ROOT_URL", app_qml_root_url)
    engine.rootContext().setContextProperty("APP_TABS_ROOT_URL", app_tabs_root_url)
    engine.rootContext().setContextProperty("STARTUP_QML_DIR_URL", app_qml_root_url)

    engine.load(QUrl.fromLocalFile(str((QML_DIR / "Splash.qml").resolve())))
    app.processEvents()

    if not engine.rootObjects():
        raise AssertionError("Splash.qml failed to load: engine.rootObjects() is empty")

    import_failures = [w for w in runtime_warnings if any(t in w.lower() for t in ("module", "import", "not installed"))]
    if import_failures:
        raise AssertionError("Runtime QML import errors:\n" + "\n".join(import_failures))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
