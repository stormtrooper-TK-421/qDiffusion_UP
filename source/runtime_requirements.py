from __future__ import annotations

from importlib.metadata import PackageNotFoundError, distribution

from packaging.requirements import Requirement


def missing_python_requirements(requirements: list[str], enforce_version: bool = True) -> list[str]:
    missing = []
    for requirement_text in requirements:
        try:
            requirement = Requirement(requirement_text)
            package_distribution = distribution(requirement.name)
            if enforce_version and requirement.specifier and not requirement.specifier.contains(package_distribution.version):
                missing.append(requirement_text)
        except PackageNotFoundError:
            missing.append(requirement_text)
        except Exception:
            pass
    return missing
