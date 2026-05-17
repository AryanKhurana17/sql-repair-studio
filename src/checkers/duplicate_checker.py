"""
Duplicate-key checker.

Detects rows that violate the primary key uniqueness constraint defined
in the schema.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.checkers.base import BaseChecker
from src.models import Issue


class DuplicateChecker(BaseChecker):
    """Detect duplicate values in the primary key column."""

    @property
    def name(self) -> str:
        return "Duplicate Keys"

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
        pk = schema.get("primary_key")

        if not pk or pk not in raw_df.columns:
            return issues

        dup_mask = raw_df.duplicated(subset=[pk], keep=False)
        dup_count = int(dup_mask.sum())

        if dup_count == 0:
            return issues

        dup_ids = raw_df.loc[dup_mask, pk].unique().tolist()
        sample = raw_df.loc[dup_mask].head(5).to_dict(orient="records")

        sql = (
            f"-- Deduplicate by keeping the first occurrence of each '{pk}'\n"
            f"WITH ranked AS (\n"
            f"    SELECT\n"
            f"        *,\n"
            f"        ROW_NUMBER() OVER (PARTITION BY {pk} ORDER BY {pk}) AS _rn\n"
            f"    FROM raw_data\n"
            f")\n"
            f"SELECT * EXCLUDE (_rn)\n"
            f"FROM ranked\n"
            f"WHERE _rn = 1;"
        )

        issues.append(
            Issue(
                category="duplicate_key",
                level=self.level,
                column=pk,
                description=(
                    f"Primary key '{pk}' has {len(dup_ids)} duplicate value(s) "
                    f"affecting {dup_count} total rows. "
                    f"Duplicates: {dup_ids[:5]}{'...' if len(dup_ids) > 5 else ''}"
                ),
                affected_rows=dup_count,
                examples=sample,
                sql_fix=sql,
                severity="critical",
            )
        )

        return issues
