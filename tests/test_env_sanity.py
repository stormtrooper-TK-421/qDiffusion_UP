from __future__ import annotations

import os
from pathlib import Path


REQUIRED_ENV = {
    "QML_DISABLE_DISK_CACHE": "1",
    "QT_DISABLE_SHADER_DISK_CACHE": "1",
    "QSG_RHI_DISABLE_SHADER_DISK_CACHE": "1",
    "PYTHONNOUSERSITE": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
}


def test_required_env_flags_are_set() -> None:
    missing = {key: expected for key, expected in REQUIRED_ENV.items() if os.environ.get(key) != expected}
    assert not missing, f"Missing or invalid hermetic env settings: {missing}"


def test_no_pyqt_imports_in_source_tree() -> None:
    pyqt_files = []
    for path in Path("source").rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        if "PyQt5" in content:
            pyqt_files.append(str(path))
    assert not pyqt_files, "PyQt imports found in source tree: " + ", ".join(sorted(pyqt_files))


def test_no_pyqt_references_in_qml_tree() -> None:
    pyqt_qml_files = []
    for path in Path("source").rglob("*.qml"):
        content = path.read_text(encoding="utf-8")
        if "PyQt5" in content:
            pyqt_qml_files.append(str(path))
    assert not pyqt_qml_files, "PyQt references found in QML tree: " + ", ".join(sorted(pyqt_qml_files))
