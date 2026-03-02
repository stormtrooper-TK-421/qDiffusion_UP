from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonType
from PySide6.QtWidgets import QApplication

import misc
from scripts import qml_smoke_test


def _build_engine(app: QApplication) -> QQmlApplicationEngine:
    engine = QQmlApplicationEngine()
    translator = qml_smoke_test._Translator(app)
    coordinator = qml_smoke_test._Coordinator(app)

    qmlRegisterSingletonType(qml_smoke_test._Translator, "gui", 1, 0, "TRANSLATOR", lambda _engine: translator)
    qmlRegisterSingletonType(QUrl("qrc:/Common.qml"), "gui", 1, 0, "COMMON")
    qmlRegisterSingletonType(qml_smoke_test._Coordinator, "gui", 1, 0, "COORDINATOR", lambda _engine: coordinator)
    misc.registerTypes()
    return engine


def _assert_qml_loads(engine: QQmlApplicationEngine, qml_url: str) -> None:
    warnings: list[str] = []

    def _record_warnings(runtime_warnings: list[object]) -> None:
        warnings.extend(str(warning) for warning in runtime_warnings)

    engine.warnings.connect(_record_warnings)
    engine.load(QUrl(qml_url))
    QApplication.processEvents()

    assert engine.rootObjects(), f"{qml_url} failed to load: rootObjects() is empty"
    assert not warnings, f"QQmlApplicationEngine warnings for {qml_url}:\n" + "\n".join(warnings)


def test_qml_splash_and_main_load_without_engine_errors() -> None:
    qml_smoke_test._ensure_qrc_module()

    import qml.qml_rc  # noqa: F401

    app = QApplication.instance() or QApplication(["pytest", "--no-effects"])

    _assert_qml_loads(_build_engine(app), "qrc:/Splash.qml")
    _assert_qml_loads(_build_engine(app), "qrc:/Main.qml")
