# Video Presentation Script

> Read this word-for-word during your Loom recording. Total time: **5-6 minutes**.

---

## Before Recording

- Run `streamlit run app.py` — app opens at `localhost:8501`
- Have VS Code open with the project folder visible in the file explorer
- Close all unrelated browser tabs and notifications
- Do one practice read-through before hitting record

---

## Part 1 — Introduction (30-40 seconds)

**[Show the app with the title and metric cards visible]**

> "Hi, this is my submission for the Data Engineering assignment. I've built a Data Quality and SQL Repair Studio using Python, Streamlit, and DuckDB."

> "The app loads the raw and reference datasets, profiles them against a YAML schema, detects data quality issues, and generates runnable DuckDB SQL to fix each one."

> "You can see the profiling summary at the top — the raw dataset has 600 rows and 10 columns. The tool found 21 issues total, 7 of which are critical and 14 are warnings."

---

## Part 2 — Dataset Loading (20 seconds)

**[Point to the sidebar showing the two file uploaders]**

> "In the sidebar, you can see the two file uploaders — one for the Raw CSV and one for the Reference CSV. If you leave them empty, the app uses the provided dataset by default. But you can upload different files and the profiling will run on those instead."

---

## Part 3 — Charts (30-40 seconds)

**[Point to the bar chart and donut chart]**

> "Below the summary, there are two charts. The bar chart on the left shows how many rows are affected by each issue category. Extra Columns affects all 600 rows because the raw data has a column that's not in the schema. Format Inconsistency is next with 152 affected rows, then Out-of-Domain values at 70."

> "The donut chart on the right shows the split between schema-level and content-level issues. We have 1 schema-level issue, which is the extra column, and 20 content-level issues like nulls, duplicates, and bad formats."

---

## Part 4 — Schema Comparison (20-30 seconds)

**[Scroll down to the schema comparison table]**

> "This table compares every column in the raw data against the reference schema. You can see the checkboxes — all 9 expected columns are present in both the schema and the raw data, so they show as Match."

> "But the last row, notes, has the In Schema checkbox unchecked. It's marked as EXTRA because the raw data has this column but the schema doesn't define it."

---

## Part 5 — Issues Report (2-2.5 minutes)

**[Scroll to the Issues Report section. The first two expanders should be open.]**

> "This is the main part — the issues report. It's organized into three tabs: All Issues, Schema-Level, and Content-Level. Let me walk through a few examples."

### Duplicate Keys

**[Point to the first expander — Duplicate Key]**

> "The first issue is duplicate primary keys. 15 customer IDs appear twice in the dataset, so 30 rows are affected. You can see the severity is CRITICAL and the level is CONTENT."

> "The sample table shows the affected rows. And below that is the generated SQL fix. It uses a CTE with ROW_NUMBER partitioned by customer_id. ROW_NUMBER assigns 1, 2 within each group of duplicates, and the WHERE clause keeps only the first occurrence."

**[Click the "Validate SQL" button. Wait for the result.]**

> "I can validate this SQL right here — it executes against DuckDB in-memory. You can see it returned 585 rows, which is the original 600 minus the 15 duplicate rows."

### Date Formats

**[Scroll down to the signup_date format inconsistency issue and expand it]**

> "This is the most interesting issue. The signup_date column has dates in 6 different formats — ISO format like 2024-07-13, slash-separated like 03/01/2025, dot-separated like 23.09.2024, and even named months like 12-Mar-2024."

> "The SQL fix uses DuckDB's TRY_STRPTIME function with COALESCE. TRY_STRPTIME is the safe version of strptime — if the format doesn't match, it returns NULL instead of crashing. COALESCE tries each format in order and picks the first one that works. All dates are then converted to the standard YYYY-MM-DD format."

### Out-of-Domain Country

**[Scroll to the country out-of-domain issue]**

> "The schema says country must be one of IN, US, UK, AE, or SG. But the raw data has values like INDIA, United States, U.K., and lowercase variants like india. The SQL uses a CASE WHEN to map each bad value to the correct code."

### Extra Column (Schema-Level)

**[Click the "Schema-Level" tab]**

> "Under the Schema-Level tab, there's one issue — the extra notes column. The SQL fix simply selects only the 9 schema-defined columns, dropping notes from the output."

---

## Part 6 — Data Explorer (15-20 seconds)

**[Scroll to the Data Explorer section. Toggle between tabs.]**

> "The Data Explorer lets you browse both datasets directly. The raw data has 600 rows and 10 columns including the extra notes column. The reference data has 60 clean rows with 9 columns."

---

## Part 7 — Combined SQL Pipeline (20-30 seconds)

**[Scroll to the Combined SQL Pipeline section]**

> "At the bottom, the tool generates a single combined CTE query that chains all the individual fixes together. Each fix becomes a named step — fix_1_duplicate_key, fix_2_null_violation, and so on. They feed into each other sequentially, so you can copy this entire block into a pipeline and clean the dataset in one pass."

---

## Part 8 — Code Architecture (1-1.5 minutes)

**[Switch to VS Code. Show the project file tree in the sidebar.]**

> "Let me quickly show the code structure. The project has a src folder with the core logic."

**[Open `src/checkers/base.py`]**

> "Every checker inherits from this BaseChecker class. It has three things — a name, a level which is either schema or content, and a check method that takes the data and schema and returns a list of Issue objects."

**[Open `src/checkers/__init__.py`]**

> "This file handles auto-discovery. It uses pkgutil to scan the checkers folder for Python files and dynamically imports each one. Any class that inherits from BaseChecker is automatically picked up by the engine."

**[Open `src/engine.py`]**

> "The engine runs all discovered checkers and collects the issues. Each checker is wrapped in a try-except, so if one checker has a bug, it reports an error instead of crashing the entire app. The other checkers still run normally."

> "The key thing is — if I want to add a new issue type, say outlier detection, I just create a new file in the checkers folder and implement the three methods. I don't need to change the engine or the app at all."

> "To ensure the system's reliability as the pipeline grows, I've also implemented unit tests using Pytest and set up a GitHub Actions CI pipeline. This ensures any new checkers won't break the core SQL execution logic."

---

## Part 9 — Closing (15 seconds)

**[Switch back to the Streamlit app]**

> "To summarize — the tool loads the raw and reference datasets, detects 21 issues across 10 categories, and generates valid DuckDB SQL for each one. Everything runs locally with no paid APIs. Thanks for watching."

---

## Key Points Checklist

Make sure you've mentioned all of these during the video:

- [ ] DuckDB — in-process, no server needed
- [ ] TRY_STRPTIME — safe date parsing, returns NULL instead of crashing
- [ ] ROW_NUMBER — window function for deduplication
- [ ] COALESCE — tries multiple date formats in order
- [ ] Auto-discovery — new checker = one new file, no engine changes
- [ ] try-except — one bad checker doesn't crash the whole app
- [ ] No paid APIs or LLMs
