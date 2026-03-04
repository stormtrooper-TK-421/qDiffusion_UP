#!/usr/bin/env python3
"""Sync canonical inference requirements from source/sd-inference-server/requirements.txt."""

from __future__ import annotations

import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_REQUIREMENTS = REPO_ROOT / "source" / "sd-inference-server" / "requirements.txt"
CANONICAL_REQUIREMENTS = REPO_ROOT / "requirements" / "inference-server.txt"


def _normalize_requirements(contents: str) -> str:
    lines: list[str] = []
    for raw_line in contents.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        lines.append(line)
    return "\n".join(lines) + "\n"


def sync_infer_requirements() -> bool:
    if not SOURCE_REQUIREMENTS.is_file():
        raise SystemExit(f"Missing inference requirements source: {SOURCE_REQUIREMENTS}")

    normalized = _normalize_requirements(SOURCE_REQUIREMENTS.read_text(encoding="utf-8"))

    source_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    header = (
        "# Auto-generated from source/sd-inference-server/requirements.txt.\n"
        f"# Source SHA256: {source_hash}\n"
        "# Do not edit manually; run scripts/sync_infer_requirements.py instead.\n\n"
    )
    output = header + normalized

    existing = CANONICAL_REQUIREMENTS.read_text(encoding="utf-8") if CANONICAL_REQUIREMENTS.is_file() else None
    if existing == output:
        print(f"[sync-infer-requirements] Up to date: {CANONICAL_REQUIREMENTS.relative_to(REPO_ROOT)}")
        return False

    CANONICAL_REQUIREMENTS.parent.mkdir(parents=True, exist_ok=True)
    CANONICAL_REQUIREMENTS.write_text(output, encoding="utf-8")
    print(
        "[sync-infer-requirements] Wrote canonical requirements: "
        f"{CANONICAL_REQUIREMENTS.relative_to(REPO_ROOT)}"
    )
    return True


def main() -> int:
    sync_infer_requirements()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
