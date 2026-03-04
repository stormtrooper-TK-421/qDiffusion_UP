#!/usr/bin/env python3
"""Fetch/update sd-inference-server into the repository source tree."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pygit2

DEFAULT_URL = "https://github.com/stormtrooper-TK-421/sd-inference-server"
ALLOWED_URLS = {DEFAULT_URL}
DEFAULT_DEST = "source/sd-inference-server"
STATE_FILE = "source/sd_infer_state.json"
LEGACY_DEST = ".third_party/sd-inference-server"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def validate_dest(repo_root: Path, raw_dest: str) -> Path:
    repo_root = repo_root.resolve()
    dest = (repo_root / raw_dest).resolve()
    try:
        dest.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError("destination outside repository") from exc
    return dest


def is_git_repo(dest: Path) -> bool:
    try:
        pygit2.Repository(str(dest))
        return True
    except (KeyError, pygit2.GitError):
        return False


def verify_invariants(dest: Path) -> None:
    if (dest / ".gitmodules").exists():
        fail(f"Submodules are forbidden: found {dest / '.gitmodules'}")
    if not (dest / "server.py").is_file():
        fail(f"Missing required file: {dest / 'server.py'}")
    if not (dest / "requirements.txt").is_file():
        fail(f"Missing required file: {dest / 'requirements.txt'}")


def _normalize_url(url: str) -> str:
    return url.rstrip("/").removesuffix(".git")


def ensure_origin(repo: pygit2.Repository, expected_url: str, dest: Path) -> pygit2.Remote:
    remote = repo.remotes.get("origin")
    if remote is None:
        fail(f"Missing origin remote in {dest}")
    if _normalize_url(remote.url) != _normalize_url(expected_url):
        fail(f"Origin URL mismatch at {dest}: expected {expected_url}, got {remote.url}")
    return remote


def _resolve_remote_default_ref(repo: pygit2.Repository) -> pygit2.Reference:
    for ref_name in (
        "refs/remotes/origin/HEAD",
        "refs/remotes/origin/main",
        "refs/remotes/origin/master",
    ):
        ref = repo.references.get(ref_name)
        if ref is None:
            continue
        if ref.type == pygit2.enums.ReferenceType.SYMBOLIC:
            try:
                ref = ref.resolve()
            except pygit2.GitError:
                continue
        return ref
    fail("Unable to determine remote default branch (origin/HEAD, origin/main, origin/master missing)")


def _clean_untracked(repo: pygit2.Repository, dest: Path) -> None:
    status = repo.status(untracked_files="all")
    for rel_path, flags in status.items():
        if flags & (pygit2.GIT_STATUS_WT_NEW | pygit2.GIT_STATUS_IGNORED):
            target = (dest / rel_path).resolve()
            try:
                target.relative_to(dest)
            except ValueError:
                continue
            if not target.exists():
                continue
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            else:
                target.unlink(missing_ok=True)


def sync_to_remote_default(repo: pygit2.Repository, dest: Path, expected_url: str) -> None:
    remote = ensure_origin(repo, expected_url, dest)
    callbacks = pygit2.RemoteCallbacks()
    remote.fetch(callbacks=callbacks)

    default_ref = _resolve_remote_default_ref(repo)
    target_oid = default_ref.target
    if target_oid is None:
        fail(f"Resolved default ref {default_ref.name} has no target")

    repo.reset(target_oid, pygit2.GIT_RESET_HARD)
    _clean_untracked(repo, dest)


def write_state(repo_root: Path, dest: Path, url: str) -> None:
    repo = pygit2.Repository(str(dest))
    commit = str(repo.head.target)
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

    repo = pygit2.Repository(str(dest))
    ensure_origin(repo, url, dest)


def clone_repo(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        pygit2.clone_repository(url, str(dest))
    except pygit2.GitError as exc:
        fail(f"Clone failed: {exc}")


def main() -> None:
    args = parse_args()

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
        clone_repo(args.url, dest)
    else:
        if not is_git_repo(dest):
            fail(f"Destination exists but is not a git repository: {dest}")

    repo = pygit2.Repository(str(dest))
    sync_to_remote_default(repo, dest, args.url)
    verify_invariants(dest)
    write_state(repo_root, dest, args.url)
    print(f"sd-inference-server ready at {dest}")


if __name__ == "__main__":
    main()
