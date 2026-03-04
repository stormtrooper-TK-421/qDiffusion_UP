from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ".third_party/sd-inference-server"
ALLOWLIST = {
    Path("scripts/fetch_sd_infer.py"),
    Path("tests/test_no_legacy_third_party_refs.py"),
}
SKIP_DIRS = {".git", ".venv", ".tmp", "__pycache__"}


def test_no_legacy_third_party_path_references() -> None:
    violations: list[str] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        rel = path.relative_to(REPO_ROOT)
        if rel in ALLOWLIST:
            continue
        if path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pyc"}:
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        if FORBIDDEN in content:
            violations.append(rel.as_posix())

    assert not violations, (
        "Found stale legacy inference checkout references to "
        f"{FORBIDDEN}: {', '.join(sorted(violations))}"
    )
