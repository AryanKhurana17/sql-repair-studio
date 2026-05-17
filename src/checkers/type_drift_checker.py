"""
Type-drift checker.

Detects values that have the right *semantic* meaning but the wrong
*representation* — for example ``"Y"`` / ``"1"`` / ``"TRUE"`` instead
of the expected ``"true"`` for a boolean column, or ``"Enterprise"``
instead of ``"enterprise"`` for a lowercase enum.

This is different from the DomainChecker in that type drift implies the
value is a *variant encoding* of a valid value, not a completely unknown
value.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.checkers.base import BaseChecker
from src.models import Issue


# ── Known equivalence maps for common type-drift patterns ─────────────────

_BOOLEAN_TRUTHY = {"y", "yes", "1", "true", "t", "on", "TRUE", "True", "Y", "YES"}
_BOOLEAN_FALSY = {"n", "no", "0", "false", "f", "off", "FALSE", "False", "N", "NO"}


class TypeDriftChecker(BaseChecker):
    """Detect values that encode the right meaning in the wrong format."""

    @property
    def name(self) -> str:
        return "Type Drift"

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
            col_type = col_spec.get("type", "")
            domain = col_spec.get("domain")

            if col_name not in raw_df.columns:
                continue

            # ── Boolean type drift ────────────────────────────────────────
            if col_type == "boolean" and domain:
                valid_set = set(domain)  # e.g. {"true", "false"}
                raw_vals = raw_df[col_name].str.strip()
                bad_mask = ~raw_vals.isin(valid_set) & (raw_vals != "")

                bad_count = int(bad_mask.sum())
                if bad_count == 0:
                    continue

                bad_vals = raw_vals[bad_mask].unique().tolist()
                sample = raw_df.loc[bad_mask].head(5).to_dict(orient="records")

                # Build CASE WHEN for known boolean variants
                case_lines = []
                for bv in sorted(set(bad_vals)):
                    if bv.lower() in {v.lower() for v in _BOOLEAN_TRUTHY}:
                        case_lines.append(f"        WHEN '{bv}' THEN 'true'")
                    elif bv.lower() in {v.lower() for v in _BOOLEAN_FALSY}:
                        case_lines.append(f"        WHEN '{bv}' THEN 'false'")
                    else:
                        case_lines.append(
                            f"        WHEN '{bv}' THEN 'false'  "
                            f"-- unmapped, defaulting to false"
                        )

                cases = "\n".join(case_lines)
                sql = (
                    f"-- Fix: Normalize boolean '{col_name}' to 'true'/'false'\n"
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
                        category="type_drift",
                        level=self.level,
                        column=col_name,
                        description=(
                            f"Column '{col_name}' (type: {col_type}) has "
                            f"{bad_count} value(s) using alternative encodings "
                            f"instead of the expected {domain}. "
                            f"Found: {bad_vals[:5]}"
                        ),
                        affected_rows=bad_count,
                        examples=sample,
                        sql_fix=sql,
                        severity="warning",
                    )
                )

            # ── Casing drift for string enums ─────────────────────────────
            # This is handled if domain checker catches them, but we also
            # specifically flag casing issues for string columns with domain
            elif col_type == "string" and domain:
                raw_vals = raw_df[col_name].str.strip()
                # Find values that match case-insensitively but not exactly
                case_drift = raw_vals.apply(
                    lambda v: v.lower() in {d.lower() for d in domain}
                    and v not in domain
                )
                drift_count = int(case_drift.sum())

                if drift_count == 0:
                    continue

                drift_vals = raw_vals[case_drift].unique().tolist()
                sample = raw_df.loc[case_drift].head(5).to_dict(orient="records")

                case_lines = []
                for dv in sorted(set(drift_vals)):
                    correct = [d for d in domain if d.lower() == dv.lower()][0]
                    case_lines.append(f"        WHEN '{dv}' THEN '{correct}'")

                cases = "\n".join(case_lines)
                sql = (
                    f"-- Fix: Correct casing in '{col_name}'\n"
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
                        category="type_drift",
                        level=self.level,
                        column=col_name,
                        description=(
                            f"Column '{col_name}' has {drift_count} value(s) "
                            f"with incorrect casing (e.g. {drift_vals[:3]}). "
                            f"Expected: {domain}"
                        ),
                        affected_rows=drift_count,
                        examples=sample,
                        sql_fix=sql,
                        severity="warning",
                    )
                )

        return issues
