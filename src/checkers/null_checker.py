"""
Null-violation checker.

Flags columns that the schema declares as ``nullable: false`` but contain
empty / null values in the raw dataset.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.checkers.base import BaseChecker
from src.models import Issue


class NullChecker(BaseChecker):
    """Detect null / empty values in non-nullable columns."""

    @property
    def name(self) -> str:
        return "Null Violations"

    @property
    def level(self) -> str:
        return "content"

    def check(
        self,
        raw_df: pd.DataFrame,
        ref_df: pd.DataFrame,
        schema: dict[str, Any],
    ) -> list[Issue]:
        issues: list[Issue] = []

        for col_spec in schema["columns"]:
            col_name = col_spec["name"]
            if col_spec.get("nullable", True):
                continue
            if col_name not in raw_df.columns:
                continue

            # A value is "null" if it is an empty string (we loaded as str)
            mask = raw_df[col_name].str.strip() == ""
            null_count = int(mask.sum())

            if null_count == 0:
                continue

            sample = raw_df.loc[mask].head(5).to_dict(orient="records")

            sql = (
                f"-- Remove rows where non-nullable column '{col_name}' is empty\n"
                f"SELECT *\n"
                f"FROM raw_data\n"
                f"WHERE TRIM(COALESCE({col_name}, '')) != '';"
            )

            issues.append(
                Issue(
                    category="null_violation",
                    level=self.level,
                    column=col_name,
                    description=(
                        f"Column '{col_name}' is non-nullable but has "
                        f"{null_count} empty/null value(s)."
                    ),
                    affected_rows=null_count,
                    examples=sample,
                    sql_fix=sql,
                    severity="critical",
                )
            )

        return issues
