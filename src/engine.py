"""
Profiling engine — runs all checkers and validates SQL.
"""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

from src.checkers import get_all_checkers
from src.models import Issue


def run_profiling(
    raw_df: pd.DataFrame,
    ref_df: pd.DataFrame,
    schema: dict[str, Any],
) -> list[Issue]:
    """Execute all registered checkers and return aggregated issues."""
    checkers = get_all_checkers()
    all_issues: list[Issue] = []

    for checker in checkers:
        try:
            issues = checker.check(raw_df, ref_df, schema)
            all_issues.extend(issues)
        except Exception as exc:
            all_issues.append(
                Issue(
                    category="engine_error",
                    level="schema",
                    column="*",
                    description=(
                        f"Checker '{checker.name}' raised an error: {exc}"
                    ),
                    affected_rows=0,
                    severity="info",
                )
            )

    # Sort: critical first, then warning, then info
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    all_issues.sort(key=lambda i: (severity_order.get(i.severity, 9), i.category))

    return all_issues


def validate_sql(
    sql: str,
    raw_df: pd.DataFrame,
) -> tuple[bool, str, pd.DataFrame | None]:
    """Execute a SQL fix statement against DuckDB and return the result."""
    try:
        con = duckdb.connect(":memory:")
        con.register("raw_data", raw_df)
        result = con.execute(sql).fetchdf()
        con.close()
        return True, f"SQL executed successfully — {len(result)} rows returned.", result
    except Exception as exc:
        return False, f"SQL execution error: {exc}", None


def get_summary_stats(
    raw_df: pd.DataFrame,
    ref_df: pd.DataFrame,
    schema: dict[str, Any],
    issues: list[Issue],
) -> dict[str, Any]:
    """Compute high-level summary statistics for the dashboard."""
    schema_issues = [i for i in issues if i.level == "schema"]
    content_issues = [i for i in issues if i.level == "content"]

    return {
        "raw_rows": len(raw_df),
        "raw_cols": len(raw_df.columns),
        "ref_rows": len(ref_df),
        "ref_cols": len(ref_df.columns),
        "schema_cols": len(schema.get("columns", [])),
        "total_issues": len(issues),
        "schema_issues": len(schema_issues),
        "content_issues": len(content_issues),
        "critical_count": sum(1 for i in issues if i.severity == "critical"),
        "warning_count": sum(1 for i in issues if i.severity == "warning"),
        "total_affected_rows": sum(i.affected_rows for i in issues),
        "checkers_run": len(get_all_checkers()),
    }
