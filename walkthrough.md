# Data Quality & SQL Repair Studio — Explanation Guide

> This document covers the dataset, why I chose certain tools, how the code works, and things I'd improve with more time.

---

## 1. The Dataset

We have three input files:

| File | Path | What it is |
|---|---|---|
| Schema | `data/reference/schema.yml` | Defines the rules — what the data should look like |
| Reference CSV | `data/reference/customers_reference.csv` | 60 clean, correctly formatted rows |
| Raw CSV | `data/raw/customers_raw.csv` | 600 messy rows with real-world data quality issues |

### Schema (`schema.yml`)

The schema is a YAML file that defines the expected structure for the `customers` table:

```yaml
table: customers
primary_key: customer_id

columns:
  - name: customer_id
    type: string
    nullable: false
    unique: true
    format: "^C\\d{6}$"        # C followed by 6 digits

  - name: email
    type: string
    nullable: false
    format: "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$"

  - name: signup_date
    type: date
    nullable: false
    format: "YYYY-MM-DD"

  - name: country
    type: string
    nullable: false
    domain: ["IN", "US", "UK", "AE", "SG"]

  - name: segment
    type: string
    nullable: false
    domain: ["retail", "premium", "enterprise"]

  - name: is_active
    type: boolean
    nullable: false
    domain: ["true", "false"]
```

Key terms:
- **nullable** — can the column have empty values?
- **unique** — must all values be distinct?
- **format** — a regex pattern the value must match
- **domain** — a whitelist of the only allowed values

### Raw vs Reference

| Property | Reference | Raw |
|---|---|---|
| Rows | 60 | 600 |
| Columns | 9 | 10 (extra `notes` column) |
| Quality | Clean | 277+ issues |

---

## 2. What is DuckDB?

DuckDB is an **in-process SQL database** — similar to SQLite but built for analytical workloads. I chose it for this project for a few practical reasons:

- **No server required** — just `pip install duckdb`, no Docker or database setup
- **Queries pandas DataFrames directly** — `con.register("raw_data", df)` makes any DataFrame queryable via SQL
- **Has useful functions** — `TRY_STRPTIME` for safe date parsing, `EXCLUDE` for dropping columns, `regexp_matches` for regex
- **Fast for scans** — it's columnar, so scanning 600 rows for pattern violations is nearly instant

**Basic usage:**

```python
import duckdb
import pandas as pd

con = duckdb.connect(":memory:")                     # No files, no server
raw_df = pd.read_csv("data/raw/customers_raw.csv")
con.register("raw_data", raw_df)                     # DataFrame becomes a SQL table

result = con.execute("""
    SELECT country, COUNT(*) as cnt
    FROM raw_data
    GROUP BY country
""").fetchdf()  # Returns a pandas DataFrame
```

**DuckDB-specific syntax used in this project:**

| Syntax | What it does |
|---|---|
| `SELECT * EXCLUDE (col)` | Select all columns except `col` |
| `TRY_STRPTIME(val, fmt)` | Parse a date — returns NULL instead of crashing if format doesn't match |
| `regexp_matches(col, pattern)` | Regex matching |
| `regexp_replace(col, pattern, repl, 'g')` | Regex find-and-replace |

---

## 3. How the Code Works

### Project Structure

```
src/
  models.py              — Issue dataclass
  data_loader.py         — Loads CSV and YAML files
  engine.py              — Runs all checkers, validates SQL
  checkers/
    base.py              — Abstract base class for checkers
    __init__.py           — Auto-discovers checker files
    schema_checker.py     — Extra/missing columns
    null_checker.py       — Empty values in non-nullable columns
    duplicate_checker.py  — Duplicate primary keys
    format_checker.py     — Invalid formats (email, phone, date, whitespace)
    domain_checker.py     — Values outside allowed domain
    type_drift_checker.py — Wrong boolean encodings (Y, 1, TRUE)
app.py                   — Streamlit dashboard
```

### The Streamlit app

The app has two file uploaders in the sidebar — one for the raw CSV, one for the reference CSV. If you don't upload anything, it uses the provided dataset by default. Once loaded, the profiling runs automatically and the results are shown in the main area.

### The checker pattern

The assignment says: *"Adding a new issue type does not require modifying the profiling engine."*

To meet this, every checker inherits from `BaseChecker` and implements:
1. **name** — for display in the UI
2. **level** — "schema" or "content"
3. **check()** — takes the data + schema, returns a list of `Issue` objects

The engine uses `pkgutil` to scan the `src/checkers/` folder and auto-discovers all checker classes. So adding a new checker is just creating a new file — the engine picks it up without any changes.

I went with this approach because it keeps each checker focused on one thing (null checking is separate from format checking, etc.), and it's easy to test each one individually.

### How detection works (no LLMs)

Each checker uses basic Python operations — no AI or machine learning:

- **Schema checker** — compares column lists: `if column not in expected_columns`
- **Null checker** — checks for empty strings: `if value.strip() == ""`
- **Duplicate checker** — uses `pandas.duplicated()` 
- **Format checker** — regex matching: `re.match(pattern, value)`
- **Domain checker** — set membership: `if value not in allowed_list`
- **Type drift checker** — checks against known boolean variants: `if value in {"Y", "1", "TRUE"}`

### How SQL is generated

Each checker builds SQL using the actual column names and bad values it found in the data. For example, the domain checker finds `"INDIA"` in the country column and generates:

```sql
CASE TRIM(country)
    WHEN 'INDIA' THEN 'IN'
    WHEN 'india' THEN 'IN'
    ELSE TRIM(country)
END AS country
```

The SQL isn't hardcoded — it's built dynamically from whatever mismatches the checker finds.

### How SQL is validated

`validate_sql()` creates a throwaway DuckDB instance, loads the raw data into it, and actually runs the generated SQL. If the SQL has a syntax error or crashes, it catches the exception and reports the error.

```python
con = duckdb.connect(":memory:")
con.register("raw_data", raw_df)
result = con.execute(sql).fetchdf()  # If this doesn't crash, the SQL is valid
```

This is important because it proves the SQL is **runnable**, not just syntactically correct.

### Data loading decision

I read all CSV data as `dtype=str` with `keep_default_na=False`:

```python
pd.read_csv(path, dtype=str, keep_default_na=False)
```

The reason: if pandas auto-detects types, `true` becomes Python `True`, empty cells become `NaN`, and phone numbers might lose formatting. By keeping everything as strings, the checkers see exactly what's in the file — which is what we need for detecting format issues.

---

## 4. Issues Found

| # | Issue | Affected Rows | Example |
|---|---|---|---|
| 1 | Extra column (`notes`) | 600 | Column not in schema |
| 2 | Null violations | 25 | Empty `signup_date`, `email`, `city` |
| 3 | Duplicate primary keys | 30 | 15 customer IDs appear twice |
| 4 | Invalid emails | 20 | `neha.mehta89@@yahoo.com`, `krishna.joshi24` |
| 5 | Invalid phone numbers | 49 | `7358718098` (missing +91-) |
| 6 | Invalid date formats | 38 | `03/01/2025`, `23.09.2024`, `12-Mar-2024` |
| 7 | Out-of-domain country | 28 | `INDIA`, `United States`, `U.K.` |
| 8 | Out-of-domain segment | 12 | `Enterprise`, `primium`, `enterprize` |
| 9 | Boolean type drift | 30 | `Y`, `1`, `FALSE`, `no` |
| 10 | Whitespace issues | 45 | `"  Aadhya Shah"`, `"Aditya  Rao"`, `"UK "` |

See `errors_and_fixes.md` for the full breakdown with SQL for each.

---

## 5. Future Enhancements (Production Readiness)

While this tool covers the core requirements, a production-grade data engineering implementation would incorporate the following enhancements:

- **Metadata Preservation (`notes` column)** — Currently, unstructured metadata columns like `notes` are dropped if they are absent from the schema. A more robust approach would involve staging this metadata in a separate Data Lake table or a JSON blob column to preserve information like "VIP" or "duplicate account" annotations for downstream analytics.
- **Probabilistic Date Resolution** — Ambiguous date strings (e.g., `03/01/2025`) are currently parsed using a deterministic fallback strategy (MM/DD prioritized). In a production environment, integrating timezone context or source-system metadata would yield more deterministic parsing.
- **Unfixable Record Dead-lettering** — Records with heavily truncated fields (e.g., incomplete email strings) cannot be programmatically resolved. Implementing a dead-letter queue (DLQ) pattern would allow these records to be partitioned and flagged for manual data stewardship review without halting the broader ETL pipeline.
- **Conflict Resolution for Deduplication** — The current logic uses a standard `ROW_NUMBER()` window function partitioned by the primary key, retaining the first occurrence. A mature pipeline would implement deterministic tie-breaking rules (e.g., `ORDER BY last_updated DESC` or comparing non-null completeness) when resolving collisions.
---

## 6. Interview Q&A

**Q: Why DuckDB instead of SQLite or PostgreSQL?**
> DuckDB is in-process so there's nothing to install. It can query pandas DataFrames directly, and it has functions like TRY_STRPTIME and EXCLUDE that made the SQL cleaner. For a tool like this where we're doing analytical scans, it's a good fit.

**Q: How do you add a new checker?**
> Create a new Python file in `src/checkers/`, define a class that inherits from `BaseChecker`, implement the `name`, `level`, and `check()` method. The engine auto-discovers it — no other changes needed.

**Q: Why read everything as strings?**
> To see the exact values in the file. If pandas auto-detects types, it converts things like `true` to boolean, empty strings to NaN. That would mask the issues I need to detect.

**Q: How do you handle the date ambiguity?**
> I use TRY_STRPTIME with COALESCE. TRY_STRPTIME returns NULL if the format doesn't match instead of crashing. I try MM/DD first since dates like `09/21/2024` can only be MM/DD (no 21st month). For truly ambiguous ones like `03/01/2025`, it's a best guess.

**Q: What if a checker has a bug and crashes?**
> The engine wraps each checker in try/except. A crashing checker produces an error message instead of taking down the whole app. The other checkers still run.

**Q: Why Streamlit?**
> The assignment suggests Streamlit or Gradio. Streamlit has built-in support for DataFrames, code blocks, and charts, and it's pure Python — no frontend code needed.
