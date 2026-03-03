from __future__ import annotations

import importlib.util
import re
from importlib.metadata import PackageNotFoundError, distribution

_REQUIREMENT_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*)(?:\[[^\]]+\])?\s*(?P<specs>(?:[!<>=~]{1,2}\s*[^,;\s]+(?:\s*,\s*[!<>=~]{1,2}\s*[^,;\s]+)*)?)"
)
_SPECIFIER_RE = re.compile(r"\s*(?P<op>[!<>=~]{1,2})\s*(?P<version>[^,;\s]+)\s*")


def missing_python_modules(modules: tuple[str, ...] | list[str]) -> list[str]:
    return [name for name in modules if importlib.util.find_spec(name) is None]


def _parse_requirement_text(requirement_text: str) -> tuple[str, list[tuple[str, str]]] | None:
    match = _REQUIREMENT_RE.match(requirement_text)
    if not match:
        return None

    name = match.group("name")
    specifier_text = match.group("specs") or ""
    if not specifier_text:
        return name, []

    specifiers = []
    for raw_specifier in specifier_text.split(","):
        specifier_match = _SPECIFIER_RE.fullmatch(raw_specifier)
        if not specifier_match:
            return None
        specifiers.append((specifier_match.group("op"), specifier_match.group("version")))
    return name, specifiers


def _version_tokens(version_text: str) -> list[int | str]:
    tokens: list[int | str] = []
    for part in re.split(r"[._+-]", version_text):
        if not part:
            continue
        if part.isdigit():
            tokens.append(int(part))
        else:
            segments = re.findall(r"\d+|[A-Za-z]+", part)
            for segment in segments:
                tokens.append(int(segment) if segment.isdigit() else segment.lower())
    return tokens


def _compare_versions(left_version: str, right_version: str) -> int:
    left_tokens = _version_tokens(left_version)
    right_tokens = _version_tokens(right_version)

    max_length = max(len(left_tokens), len(right_tokens))
    for index in range(max_length):
        left = left_tokens[index] if index < len(left_tokens) else 0
        right = right_tokens[index] if index < len(right_tokens) else 0

        if isinstance(left, int) and isinstance(right, str):
            return 1
        if isinstance(left, str) and isinstance(right, int):
            return -1
        if left < right:
            return -1
        if left > right:
            return 1
    return 0


def _compatible_upper_bound(version_text: str) -> str | None:
    numeric_release = []
    for piece in version_text.split("."):
        numeric_piece = "".join(ch for ch in piece if ch.isdigit())
        if not numeric_piece:
            break
        numeric_release.append(int(numeric_piece))

    if len(numeric_release) < 2:
        return None

    upper = numeric_release[:-1]
    upper[-1] += 1
    return ".".join(str(part) for part in upper)


def _specifier_satisfied(installed_version: str, operator: str, required_version: str) -> bool:
    comparison = _compare_versions(installed_version, required_version)
    if operator == "==":
        return comparison == 0
    if operator == "!=":
        return comparison != 0
    if operator == ">":
        return comparison > 0
    if operator == ">=":
        return comparison >= 0
    if operator == "<":
        return comparison < 0
    if operator == "<=":
        return comparison <= 0
    if operator == "~=":
        upper_bound = _compatible_upper_bound(required_version)
        if upper_bound is None:
            return comparison >= 0
        return comparison >= 0 and _compare_versions(installed_version, upper_bound) < 0
    return True


def missing_python_requirements(requirements: list[str], enforce_version: bool = True) -> list[str]:
    missing = []
    for requirement_text in requirements:
        try:
            parsed = _parse_requirement_text(requirement_text)
            if parsed is None:
                continue

            package_name, specifiers = parsed
            package_distribution = distribution(package_name)
            if enforce_version and any(
                not _specifier_satisfied(package_distribution.version, op, required_version)
                for op, required_version in specifiers
            ):
                missing.append(requirement_text)
        except PackageNotFoundError:
            missing.append(requirement_text)
        except Exception:
            pass
    return missing
