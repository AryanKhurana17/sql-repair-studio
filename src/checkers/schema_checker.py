"""
Schema-level checker.

Detects structural mismatches between the raw dataset and the reference
schema: extra columns and missing columns.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.checkers.base import BaseChecker
from src.models import Issue


class SchemaChecker(BaseChecker):
    """Compare raw dataset columns against the reference schema definition."""

    @property
    def name(self) -> str:
        return "Schema Mismatch"

    @property
    def level(self) -> str:
        return "schema"

    def check(
        self,
        raw_df: pd.DataFrame,
        ref_df: pd.DataFrame,
        schema: dict[str, Any],
    ) -> list[Issue]:
        issues: list[Issue] = []
        expected_cols = [col["name"] for col in schema["columns"]]
        raw_cols = list(raw_df.columns)

        # ── Extra columns (in raw but not in schema) ──────────────────────
        extra = [c for c in raw_cols if c not in expected_cols]
        if extra:
            keep = [c for c in raw_cols if c not in extra]
            sql = "SELECT\n"
            sql += "    " + ",\n    ".join(keep)
            sql += "\nFROM raw_data;"
            issues.append(
                Issue(
                    category="extra_columns",
                    level=self.level,
                    column=", ".join(extra),
                    description=(
                        f"Raw dataset contains {len(extra)} column(s) not "
                        f"defined in the schema: {extra}"
                    ),
                    affected_rows=len(raw_df),
                    examples=[{"extra_columns": extra}],
                    sql_fix=sql,
                    severity="warning",
                )
            )

        # ── Missing columns (in schema but not in raw) ────────────────────
        missing = [c for c in expected_cols if c not in raw_cols]
        if missing:
            sql = "SELECT\n    *,\n"
            parts = [f"    NULL AS {col}" for col in missing]
            sql += ",\n".join(parts)
            sql += "\nFROM raw_data;"
            issues.append(
                Issue(
                    category="missing_columns",
                    level=self.level,
                    column=", ".join(missing),
                    description=(
                        f"Raw dataset is missing {len(missing)} column(s) "
                        f"defined in the schema: {missing}"
                    ),
                    affected_rows=len(raw_df),
                    examples=[{"missing_columns": missing}],
                    sql_fix=sql,
                    severity="critical",
                )
            )

        return issues
