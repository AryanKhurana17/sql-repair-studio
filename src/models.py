"""
Data models for the profiling engine.

Every data quality issue discovered by a checker is represented as an Issue
dataclass.  The Streamlit UI and the SQL generator both consume these objects,
so keeping them in a single, well-typed module avoids circular imports and
keeps the contract between layers explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Issue:
    """A single data quality issue detected by a checker.

    Attributes
    ----------
    category : str
        Machine-readable issue category, e.g. ``"null_violation"``,
        ``"duplicate_key"``.  Used to group issues in the report.
    level : str
        Either ``"schema"`` (structural problem — wrong columns, wrong types)
        or ``"content"`` (value-level problem — nulls, bad formats, etc.).
    column : str
        The column affected.  Use ``"*"`` for table-wide issues like
        duplicate primary keys or extra/missing columns.
    description : str
        A short, human-readable description shown in the report.
    affected_rows : int
        Number of rows impacted by this issue.
    examples : list[dict[str, Any]]
        A small sample (≤ 5) of affected rows for the report.
    sql_fix : str
        A runnable DuckDB / ANSI SQL statement that would fix the issue.
    severity : str
        One of ``"critical"``, ``"warning"``, or ``"info"``.
    """

    category: str
    level: str
    column: str
    description: str
    affected_rows: int
    examples: list[dict[str, Any]] = field(default_factory=list)
    sql_fix: str = ""
    severity: str = "warning"
