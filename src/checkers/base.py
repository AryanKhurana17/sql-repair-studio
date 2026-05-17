"""
Abstract base class for all data quality checkers.

Every new issue type is implemented as a subclass of ``BaseChecker``.
The profiling engine discovers subclasses automatically — no registration
or engine modification required.

Design rationale
----------------
The Open/Closed Principle (OCP) is the key design driver here.  The engine
is *closed* for modification but *open* for extension: drop a new Python
file in ``src/checkers/`` that subclasses ``BaseChecker``, and it will be
picked up on the next run.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from src.models import Issue


class BaseChecker(ABC):
    """Interface that every checker must implement.

    Subclasses provide:
    - ``name``  — a short human-readable label (e.g. "Null Violations").
    - ``level`` — either ``"schema"`` or ``"content"``.
    - ``check`` — the core detection + SQL generation logic.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for the issue category."""
        ...

    @property
    @abstractmethod
    def level(self) -> str:
        """``'schema'`` for structural issues, ``'content'`` for value-level."""
        ...

    @abstractmethod
    def check(
        self,
        raw_df: pd.DataFrame,
        ref_df: pd.DataFrame,
        schema: dict[str, Any],
    ) -> list[Issue]:
        """Run the check and return zero or more ``Issue`` objects.

        Parameters
        ----------
        raw_df : pd.DataFrame
            The raw / messy dataset (all columns read as strings).
        ref_df : pd.DataFrame
            The clean reference dataset.
        schema : dict
            Parsed ``schema.yml`` dictionary.

        Returns
        -------
        list[Issue]
            One ``Issue`` per distinct problem found.  Each issue includes
            a ``sql_fix`` field with runnable DuckDB SQL.
        """
        ...
