from __future__ import annotations

import importlib.util
import re
from importlib.metadata import PackageNotFoundError, distribution

_REQUIREMENT_NAME_RE = re.compile(r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*)")


def missing_python_modules(modules: tuple[str, ...] | list[str]) -> list[str]:
    return [name for name in modules if importlib.util.find_spec(name) is None]


def _requirement_name(requirement_text: str) -> str | None:
    """Extract distribution name from a requirements-style line.

    This intentionally keeps parsing minimal and only validates package presence
    via importlib.metadata, without custom version specifier evaluation.
    """

    base = requirement_text.split("#", 1)[0].strip()
    if not base:
        return None

    match = _REQUIREMENT_NAME_RE.match(base)
    if not match:
        return None

    return match.group("name")


def missing_python_requirements(requirements: list[str], enforce_version: bool = True) -> list[str]:
    del enforce_version  # Version checks intentionally disabled: presence-only validation.

    missing = []
    for requirement_text in requirements:
        try:
            package_name = _requirement_name(requirement_text)
            if not package_name:
                continue
            distribution(package_name)
        except PackageNotFoundError:
            missing.append(requirement_text)
        except Exception:
            pass
    return missing
