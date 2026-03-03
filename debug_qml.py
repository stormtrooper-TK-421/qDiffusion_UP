#!/usr/bin/env python3
"""Minimal QML loading diagnostic for Splash.qml."""

import os
import sys
from pathlib import Path

# Enable verbose Qt plugin and QML import diagnostics before PySide6 import.
os.environ["QT_DEBUG_PLUGINS"] = "1"
os.environ["QML_IMPORT_TRACE"] = "1"

from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication


def main() -> int:
    app = QApplication(sys.argv)
    engine = QQmlApplicationEngine()

    splash_path = Path(__file__).resolve().parent / "source" / "qml" / "Splash.qml"
    splash_url = QUrl.fromLocalFile(str(splash_path))

    print(f"[debug_qml] About to call engine.load() for: {splash_url.toString()}", flush=True)
    engine.load(splash_url)
    print("[debug_qml] Returned from engine.load()", flush=True)

    if not engine.rootObjects():
        print("[debug_qml] No root objects were created; QML failed to load.", flush=True)
        return 1

    print("[debug_qml] QML loaded successfully; entering event loop.", flush=True)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
