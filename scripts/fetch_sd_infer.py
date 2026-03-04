#!/usr/bin/env python3
"""Fetch/update sd-inference-server into the repository source tree."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_URL = "https://github.com/stormtrooper-TK-421/sd-inference-server"
ALLOWED_URLS = {DEFAULT_URL}
DEFAULT_DEST = "source/sd-inference-server"
STATE_FILE = "source/sd_infer_state.json"
LEGACY_DEST = ".third_party/sd-inference-server"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def run(cmd: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        details = stderr or stdout or "(no output)"
        fail(f"Command failed ({' '.join(cmd)}): {details}")
    return result.stdout.strip()


def validate_dest(repo_root: Path, raw_dest: str) -> Path:
    repo_root = repo_root.resolve()
    dest = (repo_root / raw_dest).resolve()
    try:
        dest.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError("destination outside repository") from exc
    return dest


def git_exists() -> None:
    if shutil.which("git") is None:
        fail("git is required but was not found in PATH")


def is_git_repo(dest: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "--is-inside-work-tree"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def verify_invariants(dest: Path) -> None:
    if (dest / ".gitmodules").exists():
        fail(f"Submodules are forbidden: found {dest / '.gitmodules'}")
    if not (dest / "server.py").is_file():
        fail(f"Missing required file: {dest / 'server.py'}")
    if not (dest / "requirements.txt").is_file():
        fail(f"Missing required file: {dest / 'requirements.txt'}")


def ensure_origin(dest: Path, expected_url: str) -> None:
    origin = run(["git", "-C", str(dest), "remote", "get-url", "origin"])
    if origin != expected_url:
        fail(f"Origin URL mismatch at {dest}: expected {expected_url}, got {origin}")


def sync_to_remote_default(dest: Path) -> None:
    run(["git", "-C", str(dest), "fetch", "origin"])
    default_ref = run(
        [
            "git",
            "-C",
            str(dest),
            "symbolic-ref",
            "-q",
            "refs/remotes/origin/HEAD",
        ]
    )
    if not default_ref:
        fail("Unable to determine remote default branch (origin/HEAD)")
    run(["git", "-C", str(dest), "reset", "--hard", default_ref])
    run(["git", "-C", str(dest), "clean", "-xdf"])


def write_state(repo_root: Path, dest: Path, url: str) -> None:
    commit = run(["git", "-C", str(dest), "rev-parse", "HEAD"])
    state_path = repo_root / STATE_FILE
    state_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "url": url,
        "path": str(dest.relative_to(repo_root)),
        "commit": commit,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    state_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh", action="store_true", help="delete destination and clone again")
    parser.add_argument("--url", default=DEFAULT_URL, help="git URL to use")
    parser.add_argument("--dest", default=DEFAULT_DEST, help="destination path under repo root")
    parser.add_argument(
        "--allow-nondefault",
        action="store_true",
        help="allow URLs outside the default allowlist",
    )
    return parser.parse_args()


def migrate_legacy_checkout(repo_root: Path, dest: Path, url: str) -> None:
    legacy_dest = (repo_root / LEGACY_DEST).resolve()
    if dest.exists() or not legacy_dest.exists():
        return

    print(
        "[fetch_sd_infer] Migration: detected legacy .third_party checkout; "
        "moving it to source/sd-inference-server."
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(legacy_dest), str(dest))

    if not is_git_repo(dest):
        shutil.rmtree(dest, ignore_errors=True)
        fail("Migrated legacy checkout is not a valid git repository; rerun with --fresh to reclone cleanly.")

    ensure_origin(dest, url)


def main() -> None:
    args = parse_args()
    git_exists()

    repo_root = Path(__file__).resolve().parent.parent

    if args.url not in ALLOWED_URLS and not args.allow_nondefault:
        fail("URL is not in allowlist; pass --allow-nondefault to override")

    try:
        dest = validate_dest(repo_root, args.dest)
    except ValueError:
        fail("--dest must remain under the repository root")

    migrate_legacy_checkout(repo_root, dest, args.url)

    if args.fresh and dest.exists():
        shutil.rmtree(dest)

    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--no-recurse-submodules", args.url, str(dest)])
    else:
        if not is_git_repo(dest):
            fail(f"Destination exists but is not a git repository: {dest}")
        ensure_origin(dest, args.url)

    sync_to_remote_default(dest)
    verify_invariants(dest)
    write_state(repo_root, dest, args.url)
    print(f"sd-inference-server ready at {dest}")


if __name__ == "__main__":
    main()
