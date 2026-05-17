# Data Quality & SQL Repair Studio

A web application that loads raw and reference customer datasets, profiles them for data quality issues, and generates **runnable DuckDB SQL** to fix each one.

## Quick Start

```bash
# Clone and run in a single command
git clone <repo-url> && cd HealthKart && pip install -r requirements.txt && streamlit run app.py
```

The app opens at `http://localhost:8501`. Upload the raw and reference CSV files in the sidebar, or click "Use provided dataset" to profile the included data.

## Project Structure

```
app.py                          — Streamlit web application
requirements.txt                — Python dependencies
.streamlit/config.toml          — Dark theme configuration
data/
  raw/
    customers_raw.csv           — Messy dataset (600 rows, 10 columns)
  reference/
    customers_reference.csv     — Clean dataset (60 rows, 9 columns)
    schema.yml                  — Column definitions, types, constraints
src/
  models.py                     — Issue dataclass
  data_loader.py                — CSV + YAML loading
  engine.py                     — Profiling engine (runs all checkers, validates SQL)
  checkers/
    __init__.py                 — Auto-discovers all checker files
    base.py                     — Abstract base class (BaseChecker)
    schema_checker.py           — Extra/missing column detection
    null_checker.py             — Null/empty value violations
    duplicate_checker.py        — Primary key uniqueness violations
    format_checker.py           — Regex format & whitespace issues
    domain_checker.py           — Out-of-domain value detection
    type_drift_checker.py       — Boolean/casing drift detection
```

## Adding a New Issue Type

New checkers can be added **without modifying the profiling engine**:

```python
# src/checkers/my_new_checker.py

from src.checkers.base import BaseChecker
from src.models import Issue

class MyNewChecker(BaseChecker):

    @property
    def name(self) -> str:
        return "My New Check"

    @property
    def level(self) -> str:
        return "content"  # or "schema"

    def check(self, raw_df, ref_df, schema) -> list[Issue]:
        issues = []
        # Detection logic here
        return issues
```

The auto-discovery in `src/checkers/__init__.py` finds the new subclass automatically. No imports to add, no engine changes.

## Detected Issue Types

| Issue Type | Level | Description |
|---|---|---|
| Schema Mismatch | Schema | Extra/missing columns vs schema definition |
| Null Violations | Content | Empty values in non-nullable columns |
| Duplicate Keys | Content | Duplicate primary key values |
| Format Inconsistencies | Content | Values violating regex patterns (email, phone, date) |
| Out-of-Domain Values | Content | Values outside allowed domain lists |
| Type Drift | Content | Wrong encoding of valid values (Y to true, Enterprise to enterprise) |

## Technology Stack

| Component | Technology | Why |
|---|---|---|
| Web Framework | Streamlit | Python-native, built-in DataFrame and chart support |
| SQL Engine | DuckDB | In-process, no server needed, CSV-native |
| Data Processing | pandas | Industry-standard DataFrame operations |
| Visualization | Plotly | Interactive charts |
| Schema Parsing | PyYAML | Standard YAML parsing |
| Testing & CI/CD | Pytest, GitHub Actions | Ensures robust SQL validation before deployment |

## Testing and CI/CD

To ensure the reliability of the core engine and SQL execution layer, this project includes automated tests.
Run the test suite via:

```bash
PYTHONPATH=. pytest tests/
```

Continuous Integration is configured via GitHub Actions (`.github/workflows/python-app.yml`). It automatically installs dependencies and runs the unit tests on every push to the `main` branch, ensuring that new checkers or engine modifications do not break existing functionality. This reflects standard data engineering best practices for maintaining data pipeline reliability.
