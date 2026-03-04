from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_PY = REPO_ROOT / "source" / "main.py"
QML_DIR = REPO_ROOT / "source" / "qml"
SPLASH_QML = QML_DIR / "Splash.qml"


def test_startup_qml_policy_is_disk_only() -> None:
    for startup_file in ("Splash.qml", "Installer.qml", "Main.qml", "Common.qml"):
        resolved = (QML_DIR / startup_file).resolve()
        assert resolved.exists(), f"missing startup asset: {resolved}"
        assert resolved.is_file(), f"startup asset is not a file: {resolved}"


def test_main_py_uses_disk_only_startup_urls() -> None:
    content = MAIN_PY.read_text(encoding="utf-8")

    assert "qml.qml_rc" not in content
    assert 'QUrl("qrc:/Splash.qml")' not in content
    assert 'QUrl("qrc:/Common.qml")' not in content
    assert "QUrl.fromLocalFile" in content


def test_splash_routes_startup_components_with_disk_urls() -> None:
    content = SPLASH_QML.read_text(encoding="utf-8")

    assert "STARTUP_QML_DIR_URL" in content
    assert "startupQmlDirUrl + \"/Installer.qml\"" in content
    assert "startupQmlDirUrl + \"/Main.qml\"" in content
    assert "startupQmlDirUrl + \"/icons/loading.svg\"" in content
    assert "qrc:/Installer.qml" not in content
    assert "qrc:/Main.qml" not in content
    assert "file:source/qml/icons/loading.svg" not in content
