"""
Data loading utilities.

Responsible for:
- Reading the YAML schema definition into a Python dict.
- Loading CSV files into pandas DataFrames.
- Registering DataFrames as DuckDB virtual tables so generated SQL can
  reference them by name.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import yaml


def load_schema(path: str | Path) -> dict[str, Any]:
    """Parse ``schema.yml`` into a Python dictionary.

    Parameters
    ----------
    path : str or Path
        Absolute or relative path to the YAML schema file.

    Returns
    -------
    dict
        Parsed schema with keys like ``table``, ``primary_key``, ``columns``,
        and ``expectations``.
    """
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def load_csv(path: str | Path) -> pd.DataFrame:
    """Load a CSV file into a DataFrame, keeping all values as strings.

    We read everything as ``str`` so that type-checking logic inside the
    checkers operates on raw string representations (the same thing a human
    would see when they open the file in a text editor).

    Parameters
    ----------
    path : str or Path
        Path to the CSV file.

    Returns
    -------
    pd.DataFrame
    """
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def register_tables(
    con: duckdb.DuckDBPyConnection,
    raw_df: pd.DataFrame,
    ref_df: pd.DataFrame,
) -> None:
    """Register DataFrames as DuckDB virtual tables.

    After calling this function the connection ``con`` can execute SQL that
    references ``raw_data`` and ``ref_data`` as table names.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        An open DuckDB connection (in-memory is fine).
    raw_df : pd.DataFrame
        The raw / messy dataset.
    ref_df : pd.DataFrame
        The clean reference dataset.
    """
    con.register("raw_data", raw_df)
    con.register("ref_data", ref_df)
