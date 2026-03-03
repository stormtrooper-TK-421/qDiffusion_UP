from __future__ import annotations

import importlib.util
import re
from importlib.metadata import PackageNotFoundError, distribution


def missing_python_modules(modules: tuple[str, ...] | list[str]) -> list[str]:
    return [name for name in modules if importlib.util.find_spec(name) is None]


_REQ_RE = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9._-]*)\s*(==|>=|<=|!=|~=|>|<)?\s*(.*)$")


def _version_tuple(v: str) -> tuple[int, ...]:
    parts: list[int] = []
    for segment in v.split("."):
        try:
            parts.append(int(segment))
        except ValueError:
            break
    return tuple(parts)


def _version_matches(installed: str, op: str, required: str) -> bool:
    iv, rv = _version_tuple(installed), _version_tuple(required)
    if op == "==":
        return iv == rv
    if op == ">=":
        return iv >= rv
    if op == "<=":
        return iv <= rv
    if op == ">":
        return iv > rv
    if op == "<":
        return iv < rv
    if op == "!=":
        return iv != rv
    return True


def missing_python_requirements(requirements: list[str], enforce_version: bool = True) -> list[str]:
    missing: list[str] = []
    for requirement_text in requirements:
        try:
            m = _REQ_RE.match(requirement_text.strip())
            if not m:
                continue
            name, op, ver = m.group(1), m.group(2) or "", m.group(3).strip()
            package_distribution = distribution(name)
            if enforce_version and op and ver:
                if not _version_matches(package_distribution.version, op, ver):
                    missing.append(requirement_text)
        except PackageNotFoundError:
            missing.append(requirement_text)
        except Exception:
            pass
    return missing
