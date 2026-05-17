import pandas as pd
import pytest
from src.engine import validate_sql

def test_validate_sql_success():
    df = pd.DataFrame({"id": [1, 2, 3], "val": ["a", "b", "c"]})
    sql = "SELECT * FROM raw_data WHERE id = 1"
    ok, msg, result = validate_sql(sql, df)
    assert ok is True
    assert result is not None
    assert len(result) == 1
    assert result.iloc[0]["val"] == "a"

def test_validate_sql_failure():
    df = pd.DataFrame({"id": [1, 2, 3]})
    # Intentional syntax error or non-existent table to trigger failure
    sql = "SELECT * FROM non_existent_table"
    ok, msg, result = validate_sql(sql, df)
    assert ok is False
    assert result is None
    assert "error" in msg.lower()
