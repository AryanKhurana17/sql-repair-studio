"""
Checker auto-discovery module.

When this package is imported, it:
1. Scans every ``.py`` file in ``src/checkers/`` (excluding ``__init__`` and
   ``base``).
2. Imports each module.
3. Collects every concrete subclass of ``BaseChecker``.

This means adding a new checker is as simple as creating a new file —
no imports, no registration, no engine changes.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from src.checkers.base import BaseChecker

_CHECKER_REGISTRY: list[BaseChecker] = []


def _discover_checkers() -> list[BaseChecker]:
    """Import all checker modules and instantiate concrete subclasses."""
    package_dir = Path(__file__).parent

    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if module_info.name in ("base",):
            continue
        importlib.import_module(f"src.checkers.{module_info.name}")

    # Recursively find all concrete subclasses of BaseChecker
    def _all_subclasses(cls):
        result = []
        for sub in cls.__subclasses__():
            if not getattr(sub, "__abstractmethods__", None):
                result.append(sub)
            result.extend(_all_subclasses(sub))
        return result

    return [cls() for cls in _all_subclasses(BaseChecker)]


def get_all_checkers() -> list[BaseChecker]:
    """Return instantiated checker objects (cached after first call)."""
    global _CHECKER_REGISTRY
    if not _CHECKER_REGISTRY:
        _CHECKER_REGISTRY = _discover_checkers()
    return _CHECKER_REGISTRY
