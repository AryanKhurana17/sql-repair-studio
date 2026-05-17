"""
Out-of-domain value checker.

Flags values that fall outside the allowed ``domain`` list defined in the
schema (e.g. country must be one of ``[IN, US, UK, AE, SG]``).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.checkers.base import BaseChecker
from src.models import Issue


class DomainChecker(BaseChecker):
    """Detect values that are not in the schema-defined domain list."""

    @property
    def name(self) -> str:
        return "Out-of-Domain Values"

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
            domain = col_spec.get("domain")

            if not domain or col_name not in raw_df.columns:
                continue

            # Trim values before checking domain membership
            trimmed = raw_df[col_name].str.strip()
            bad_mask = ~trimmed.isin(domain)
            # Exclude empty strings (handled by NullChecker)
            bad_mask = bad_mask & (trimmed != "")
            bad_count = int(bad_mask.sum())

            if bad_count == 0:
                continue

            # Collect the actual bad values for a smart CASE WHEN mapping
            bad_values = trimmed[bad_mask].unique().tolist()
            sample = raw_df.loc[bad_mask].head(5).to_dict(orient="records")

            # Build a smart domain-mapping SQL
            case_lines = []
            for bv in sorted(bad_values):
                # Attempt case-insensitive match first
                matched = [d for d in domain if d.lower() == bv.lower()]
                if matched:
                    case_lines.append(
                        f"        WHEN '{bv}' THEN '{matched[0]}'"
                    )
                else:
                    # Known expansions for country codes
                    known_maps = {
                        "U.K.": "UK",
                        "United Kingdom": "UK",
                        "United States": "US",
                        "U.S.": "US",
                        "U.S.A.": "US",
                        "India": "IN",
                        "United Arab Emirates": "AE",
                        "Singapore": "SG",
                    }
                    target = known_maps.get(bv, "NULL  -- UNMAPPED")
                    case_lines.append(
                        f"        WHEN '{bv}' THEN '{target}'"
                    )

            cases = "\n".join(case_lines)
            sql = (
                f"-- Fix: Map out-of-domain '{col_name}' values to valid domain\n"
                f"SELECT\n"
                f"    * EXCLUDE ({col_name}),\n"
                f"    CASE TRIM({col_name})\n"
                f"{cases}\n"
                f"        ELSE TRIM({col_name})\n"
                f"    END AS {col_name}\n"
                f"FROM raw_data;"
            )

            issues.append(
                Issue(
                    category="out_of_domain",
                    level=self.level,
                    column=col_name,
                    description=(
                        f"Column '{col_name}' has {bad_count} value(s) outside "
                        f"the allowed domain {domain}. "
                        f"Found: {bad_values[:5]}{'...' if len(bad_values) > 5 else ''}"
                    ),
                    affected_rows=bad_count,
                    examples=sample,
                    sql_fix=sql,
                    severity="warning",
                )
            )

        return issues
