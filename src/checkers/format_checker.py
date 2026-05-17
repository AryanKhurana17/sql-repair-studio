"""
Format-inconsistency checker.

Validates column values against the regex patterns defined in the schema's
``format`` field (e.g. email patterns, phone patterns, date patterns).
Also checks for leading/trailing whitespace and double-space issues in
string columns.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from src.checkers.base import BaseChecker
from src.models import Issue


# ── SQL fix templates per known format ────────────────────────────────────

_FORMAT_SQL: dict[str, str] = {
    "email": (
        "-- Fix: Normalize emails (lowercase, trim whitespace)\n"
        "SELECT\n"
        "    * EXCLUDE (email),\n"
        "    LOWER(TRIM(email)) AS email\n"
        "FROM raw_data\n"
        "WHERE NOT regexp_matches(email, '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$');"
    ),
    "phone": (
        "-- Fix: Normalize phone numbers to +CC-NNNNNNNNNN format\n"
        "SELECT\n"
        "    * EXCLUDE (phone),\n"
        "    CASE\n"
        "        -- Already valid\n"
        "        WHEN regexp_matches(phone, '^\\+\\d{1,3}-\\d{7,12}$')\n"
        "            THEN phone\n"
        "        -- Missing '+' prefix  (e.g. '91-9800667638')\n"
        "        WHEN regexp_matches(phone, '^\\d{1,3}-\\d{7,12}$')\n"
        "            THEN '+' || phone\n"
        "        -- Bare digits (e.g. '7358718098') — assume India (+91)\n"
        "        WHEN regexp_matches(phone, '^\\d{10}$')\n"
        "            THEN '+91-' || phone\n"
        "        -- Spaces instead of hyphen (e.g. '+91 85419 06299')\n"
        "        WHEN phone LIKE '+%'\n"
        "            THEN regexp_replace(\n"
        "                regexp_replace(phone, '\\s+', '', 'g'),\n"
        "                '^(\\+\\d{1,3})(\\d+)$', '\\1-\\2'\n"
        "            )\n"
        "        ELSE phone\n"
        "    END AS phone\n"
        "FROM raw_data;"
    ),
    "customer_id": (
        "-- Fix: Flag invalid customer_id formats\n"
        "SELECT *\n"
        "FROM raw_data\n"
        "WHERE regexp_matches(customer_id, '^C\\d{6}$');"
    ),
    "signup_date": (
        "-- Fix: Normalize dates to ISO 8601 (YYYY-MM-DD)\n"
        "-- Uses COALESCE + TRY_STRPTIME to attempt multiple formats safely\n"
        "SELECT\n"
        "    * EXCLUDE (signup_date),\n"
        "    CASE\n"
        "        WHEN signup_date IS NULL OR TRIM(signup_date) = '' THEN NULL\n"
        "        WHEN regexp_matches(signup_date, '^\\d{4}-\\d{2}-\\d{2}$')\n"
        "            THEN signup_date\n"
        "        ELSE strftime(\n"
        "            COALESCE(\n"
        "                TRY_STRPTIME(signup_date, '%m/%d/%Y'),\n"
        "                TRY_STRPTIME(signup_date, '%Y/%m/%d'),\n"
        "                TRY_STRPTIME(signup_date, '%d/%m/%Y'),\n"
        "                TRY_STRPTIME(signup_date, '%d.%m.%Y'),\n"
        "                TRY_STRPTIME(signup_date, '%d-%b-%Y'),\n"
        "                TRY_STRPTIME(signup_date, '%d-%m-%Y')\n"
        "            ),\n"
        "            '%Y-%m-%d'\n"
        "        )\n"
        "    END AS signup_date\n"
        "FROM raw_data;"
    ),
    "full_name": (
        "-- Fix: Trim whitespace and collapse double spaces in names\n"
        "SELECT\n"
        "    * EXCLUDE (full_name),\n"
        "    TRIM(regexp_replace(full_name, '\\s+', ' ', 'g')) AS full_name\n"
        "FROM raw_data;"
    ),
}


class FormatChecker(BaseChecker):
    """Validate column values against schema-defined regex format patterns."""

    @property
    def name(self) -> str:
        return "Format Inconsistencies"

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
            fmt = col_spec.get("format")

            if not fmt or col_name not in raw_df.columns:
                continue

            # Skip empty values — those are caught by NullChecker
            non_empty = raw_df[col_name].str.strip() != ""
            target = raw_df.loc[non_empty, col_name]

            if col_spec.get("type") == "date":
                # Date format is specified as YYYY-MM-DD — check with regex
                pattern = r"^\d{4}-\d{2}-\d{2}$"
            else:
                pattern = fmt

            try:
                bad_mask = ~target.str.match(pattern, na=False)
            except re.error:
                continue

            bad_count = int(bad_mask.sum())
            if bad_count == 0:
                continue

            bad_indices = target.index[bad_mask]
            sample = raw_df.loc[bad_indices].head(5).to_dict(orient="records")

            # Pick the best SQL template for this column
            sql = _FORMAT_SQL.get(
                col_name,
                (
                    f"-- Fix: Filter rows with invalid '{col_name}' format\n"
                    f"SELECT *\n"
                    f"FROM raw_data\n"
                    f"WHERE regexp_matches({col_name}, '{pattern}');"
                ),
            )

            issues.append(
                Issue(
                    category="format_inconsistency",
                    level=self.level,
                    column=col_name,
                    description=(
                        f"Column '{col_name}' has {bad_count} value(s) that "
                        f"do not match the expected format pattern."
                    ),
                    affected_rows=bad_count,
                    examples=sample,
                    sql_fix=sql,
                    severity="warning",
                )
            )

        # ── Extra check: whitespace issues in string columns ──────────────
        for col_spec in schema["columns"]:
            col_name = col_spec["name"]
            if col_spec.get("type") != "string" or col_name not in raw_df.columns:
                continue
            if col_spec.get("format"):
                continue  # Already handled by regex check above

            col_vals = raw_df[col_name]
            ws_mask = (col_vals != col_vals.str.strip()) | col_vals.str.contains(
                r"\s{2,}", regex=True, na=False
            )
            ws_count = int(ws_mask.sum())

            if ws_count == 0:
                continue

            sample = raw_df.loc[ws_mask].head(5).to_dict(orient="records")
            sql = _FORMAT_SQL.get(
                col_name,
                (
                    f"-- Fix: Trim whitespace in '{col_name}'\n"
                    f"SELECT\n"
                    f"    * EXCLUDE ({col_name}),\n"
                    f"    TRIM(regexp_replace({col_name}, '\\s+', ' ', 'g')) "
                    f"AS {col_name}\n"
                    f"FROM raw_data;"
                ),
            )

            issues.append(
                Issue(
                    category="format_inconsistency",
                    level=self.level,
                    column=col_name,
                    description=(
                        f"Column '{col_name}' has {ws_count} value(s) with "
                        f"leading/trailing whitespace or double spaces."
                    ),
                    affected_rows=ws_count,
                    examples=sample,
                    sql_fix=sql,
                    severity="warning",
                )
            )

        return issues
