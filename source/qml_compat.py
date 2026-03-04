from collections.abc import Callable
from typing import Any


def singleton_instance_provider(instance: Any) -> Callable[[Any], Any]:
    """Create a PySide6-compatible singleton provider returning an existing instance."""

    def _provider(_engine: Any) -> Any:
        return instance

    return _provider
