from __future__ import annotations

import sys
from pathlib import Path


def repo_root() -> Path:
    """Return the repository/runtime root directory."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass).resolve()
    return Path(__file__).resolve().parent.parent


def resource_path(rel: str | Path) -> str:
    """Resolve a path relative to the runtime root.

    Absolute paths are returned unchanged.
    """
    path = Path(rel)
    if path.is_absolute():
        return str(path)
    return str((repo_root() / path).resolve())
