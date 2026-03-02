#!/usr/bin/env python3
"""Assert repository and user-space cache policies remain enforced."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = REPO_ROOT / "source"
APP_CACHE_TOKENS = ("qdiffusion", "qdiffusion_up")


def _find_source_pycache() -> list[Path]:
    return sorted(path for path in SOURCE_ROOT.rglob("__pycache__") if path.is_dir())


def _find_repo_pip_cache() -> list[Path]:
    candidates: list[Path] = []

    known_cache_roots = [
        REPO_ROOT / ".cache" / "pip",
        REPO_ROOT / "pip-cache",
        REPO_ROOT / ".pip_cache",
        REPO_ROOT / ".tmp" / "pip",
    ]
    for root in known_cache_roots:
        if root.exists():
            candidates.append(root)

    for path in REPO_ROOT.rglob("*"):
        if not path.is_dir():
            continue
        lower = path.name.lower()
        if lower != "pip":
            continue
        try:
            rel = path.relative_to(REPO_ROOT)
        except ValueError:
            continue
        if any(part.startswith(".") for part in rel.parts[:-1]):
            continue
        marker_children = {"http", "http-v2", "wheels", "selfcheck", "cache"}
        if any((path / marker).exists() for marker in marker_children):
            candidates.append(path)

    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(path)
    return sorted(deduped)


def _qml_cache_roots() -> list[Path]:
    roots: list[Path] = []
    home = Path.home()
    env_paths = [
        os.environ.get("XDG_CACHE_HOME"),
        os.environ.get("LOCALAPPDATA"),
        os.environ.get("APPDATA"),
    ]
    for value in env_paths:
        if value:
            roots.append(Path(value))

    roots.extend(
        [
            home / ".cache",
            home / ".config",
            home / "AppData" / "Local",
            home / "AppData" / "Roaming",
            home / "Library" / "Caches",
            home / "Library" / "Preferences",
        ]
    )

    deduped: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(root)
    return deduped


def _find_qml_disk_cache() -> list[Path]:
    matches: list[Path] = []
    for root in _qml_cache_roots():
        for token in APP_CACHE_TOKENS:
            pattern = f"*{token}*"
            for path in root.glob(pattern):
                if not path.exists():
                    continue
                if path.is_dir() and any(name.lower().startswith(("qmlcache", "qtshadercache", "shadercache")) for name in os.listdir(path)):
                    matches.append(path)
                    continue
                if path.name.lower().startswith(("qmlcache", "qtshadercache", "shadercache")):
                    matches.append(path)
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in matches:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(path)
    return sorted(deduped)


def _fail(title: str, paths: list[Path]) -> None:
    print(title, file=sys.stderr)
    for path in paths:
        print(f" - {path}", file=sys.stderr)


def main() -> int:
    pycache_dirs = _find_source_pycache()
    pip_caches = _find_repo_pip_cache()
    qml_cache_dirs = _find_qml_disk_cache()

    if pycache_dirs:
        _fail("Found forbidden __pycache__ directories under source/", pycache_dirs)
    if pip_caches:
        _fail("Found forbidden pip cache directories under repository root", pip_caches)
    if qml_cache_dirs:
        _fail("Detected potential QML/Qt disk cache directories for qDiffusion", qml_cache_dirs)

    if pycache_dirs or pip_caches or qml_cache_dirs:
        return 1

    print("No forbidden cache artifacts detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
