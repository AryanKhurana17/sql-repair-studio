"""
Data Quality & SQL Repair Studio — Streamlit Web Application.

Profiles the raw customer dataset against a reference schema,
detects data quality issues, and generates DuckDB SQL to fix them.

Run with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from src.data_loader import load_csv, load_schema
from src.engine import run_profiling, validate_sql, get_summary_stats

# ── Page config ───────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Data Quality & SQL Repair Studio",
    page_icon="DQ",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar — Load Datasets ───────────────────────────────────────────────

with st.sidebar:
    st.header("Load Datasets")

    raw_file = st.file_uploader("Raw CSV", type=["csv"], key="raw_upload")
    ref_file = st.file_uploader("Reference CSV", type=["csv"], key="ref_upload")

    st.divider()
    use_default = st.button("Use provided dataset", use_container_width=True)

    st.caption(
        "Upload both files above, or click the button "
        "to use the provided dataset."
    )

    st.divider()
    st.subheader("Active Checkers")

# ── Load data ─────────────────────────────────────────────────────────────

# Track whether data has been loaded
if use_default:
    st.session_state["data_loaded"] = "default"
if raw_file and ref_file:
    st.session_state["data_loaded"] = "uploaded"


@st.cache_data
def load_default_data():
    raw_df = load_csv("data/raw/customers_raw.csv")
    ref_df = load_csv("data/reference/customers_reference.csv")
    schema = load_schema("data/reference/schema.yml")
    return raw_df, ref_df, schema


@st.cache_data
def load_uploaded_data(raw_bytes, ref_bytes):
    import io
    raw_df = pd.read_csv(io.BytesIO(raw_bytes), dtype=str, keep_default_na=False)
    ref_df = pd.read_csv(io.BytesIO(ref_bytes), dtype=str, keep_default_na=False)
    schema = load_schema("data/reference/schema.yml")
    return raw_df, ref_df, schema


if "data_loaded" not in st.session_state:
    st.title("Data Quality & SQL Repair Studio")
    st.caption("Automated data profiling, issue detection, and SQL fix generation")
    st.divider()
    st.info("Upload the raw and reference CSV files in the sidebar, or click 'Use provided dataset' to get started.")
    st.stop()

try:
    if st.session_state["data_loaded"] == "uploaded" and raw_file and ref_file:
        raw_df, ref_df, schema = load_uploaded_data(
            raw_file.read(), ref_file.read()
        )
    else:
        raw_df, ref_df, schema = load_default_data()
except Exception as e:
    st.error(f"Failed to load data: {e}")
    st.stop()

# ── Run profiling ─────────────────────────────────────────────────────────

@st.cache_data
def cached_profiling(raw_csv, ref_csv, schema_dict):
    raw_df_inner = pd.read_csv(pd.io.common.StringIO(raw_csv), dtype=str, keep_default_na=False)
    ref_df_inner = pd.read_csv(pd.io.common.StringIO(ref_csv), dtype=str, keep_default_na=False)
    return run_profiling(raw_df_inner, ref_df_inner, schema_dict)

raw_csv_str = raw_df.to_csv(index=False)
ref_csv_str = ref_df.to_csv(index=False)
issues = cached_profiling(raw_csv_str, ref_csv_str, schema)
stats = get_summary_stats(raw_df, ref_df, schema, issues)

# Show checkers in sidebar
from src.checkers import get_all_checkers
for checker in get_all_checkers():
    with st.sidebar:
        st.caption(f"**{checker.name}** — _{checker.level}_")

# ── Header ────────────────────────────────────────────────────────────────

st.title("Data Quality & SQL Repair Studio")
st.caption("Automated data profiling, issue detection, and SQL fix generation")
st.divider()

# ── Summary metrics ───────────────────────────────────────────────────────

st.subheader("Profiling Summary")

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Raw Rows", f"{stats['raw_rows']:,}")
c2.metric("Raw Columns", stats["raw_cols"])
c3.metric("Reference Rows", f"{stats['ref_rows']:,}")
c4.metric("Total Issues", stats["total_issues"])
c5.metric("Critical", stats["critical_count"])
c6.metric("Warnings", stats["warning_count"])

st.write("")

# ── Charts ────────────────────────────────────────────────────────────────

col_chart, col_donut = st.columns([3, 2])

with col_chart:
    if issues:
        cat_counts = {}
        for issue in issues:
            label = issue.category.replace("_", " ").title()
            cat_counts[label] = cat_counts.get(label, 0) + issue.affected_rows

        sorted_cats = sorted(cat_counts.items(), key=lambda x: x[1])
        labels = [x[0] for x in sorted_cats]
        values = [x[1] for x in sorted_cats]

        fig = go.Figure(
            go.Bar(
                x=values, y=labels, orientation="h",
                marker=dict(color=values, colorscale="Tealgrn"),
                text=values, textposition="auto",
            )
        )
        fig.update_layout(
            title="Affected Rows by Issue Category",
            template="plotly_dark", height=360,
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis_title=None,
        )
        st.plotly_chart(fig, use_container_width=True)

with col_donut:
    if issues:
        fig2 = go.Figure(
            go.Pie(
                labels=["Schema-Level", "Content-Level"],
                values=[stats["schema_issues"], stats["content_issues"]],
                hole=0.6,
                marker=dict(colors=["#a371f7", "#2f81f7"]),
                textinfo="label+value",
            )
        )
        fig2.update_layout(
            title="Schema vs Content Issues",
            template="plotly_dark", height=360,
            margin=dict(l=10, r=10, t=40, b=10),
            showlegend=False,
        )
        st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ── Schema comparison ────────────────────────────────────────────────────

st.subheader("Schema Comparison — Raw vs Reference")

expected_cols = [c["name"] for c in schema["columns"]]
raw_cols = list(raw_df.columns)

comparison_rows = []
for col in list(dict.fromkeys(expected_cols + raw_cols)):
    in_schema = col in expected_cols
    in_raw = col in raw_cols
    col_spec = next((c for c in schema["columns"] if c["name"] == col), {})

    if in_schema and in_raw:
        status = "Match"
    elif in_raw:
        status = "EXTRA"
    else:
        status = "MISSING"

    comparison_rows.append({
        "Column": col,
        "In Schema": in_schema,
        "In Raw": in_raw,
        "Type": col_spec.get("type", "-"),
        "Nullable": "Yes" if col_spec.get("nullable", True) else "No",
        "Allowed Values": ", ".join(col_spec["domain"]) if col_spec.get("domain") else "Any",
        "Status": status,
    })

st.dataframe(
    pd.DataFrame(comparison_rows),
    use_container_width=True, hide_index=True,
    column_config={
        "In Schema": st.column_config.CheckboxColumn("In Schema", disabled=True),
        "In Raw": st.column_config.CheckboxColumn("In Raw", disabled=True),
    },
)

st.divider()

# ── Issues report ─────────────────────────────────────────────────────────

st.subheader("Issues Report")

if not issues:
    st.success("No data quality issues found.")
else:
    tab_all, tab_schema, tab_content = st.tabs([
        f"All Issues ({len(issues)})",
        f"Schema-Level ({stats['schema_issues']})",
        f"Content-Level ({stats['content_issues']})",
    ])

    def render_issue(issue, idx, tab_key="all"):
        title = issue.category.replace("_", " ").title()
        label = f"{title}  |  Column: {issue.column}  |  {issue.affected_rows} rows affected"

        with st.expander(label, expanded=(idx < 2)):
            sev_col, lvl_col, _ = st.columns([1, 1, 6])
            with sev_col:
                if issue.severity == "critical":
                    st.error(f"**{issue.severity.upper()}**")
                else:
                    st.warning(f"**{issue.severity.upper()}**")
            with lvl_col:
                if issue.level == "schema":
                    st.info(f"**{issue.level.upper()}**")
                else:
                    st.success(f"**{issue.level.upper()}**")

            st.markdown(f"**{issue.description}**")

            if issue.examples:
                st.markdown("**Sample affected rows**")
                st.dataframe(
                    pd.DataFrame(issue.examples).head(5),
                    use_container_width=True, hide_index=True,
                )

            if issue.sql_fix:
                st.markdown("**Generated SQL fix**")
                st.code(issue.sql_fix, language="sql")

                if st.button("Validate SQL", key=f"v_{tab_key}_{idx}_{issue.category}"):
                    with st.spinner("Executing against DuckDB..."):
                        ok, msg, result_df = validate_sql(issue.sql_fix, raw_df)
                    if ok:
                        st.success(msg)
                        if result_df is not None and len(result_df) > 0:
                            st.markdown("**Result preview (first 10 rows)**")
                            st.dataframe(result_df.head(10), use_container_width=True, hide_index=True)
                            st.download_button(
                                label="Download cleaned CSV",
                                data=result_df.to_csv(index=False),
                                file_name=f"cleaned_{issue.category}.csv",
                                mime="text/csv",
                                key=f"dl_{tab_key}_{idx}_{issue.category}",
                            )
                    else:
                        st.error(msg)

    with tab_all:
        for i, issue in enumerate(issues):
            render_issue(issue, i, "all")
    with tab_schema:
        schema_issues = [x for x in issues if x.level == "schema"]
        for i, issue in enumerate(schema_issues):
            render_issue(issue, i, "sch")
    with tab_content:
        content_issues = [x for x in issues if x.level == "content"]
        for i, issue in enumerate(content_issues):
            render_issue(issue, i, "cnt")

st.divider()

# ── Data explorer ─────────────────────────────────────────────────────────

st.subheader("Data Explorer (Side-by-Side View)")

col_raw, col_ref = st.columns(2)
with col_raw:
    st.markdown("**Raw Dataset**")
    st.caption(f"{len(raw_df):,} rows, {len(raw_df.columns)} columns")
    st.dataframe(raw_df, use_container_width=True, height=400)
with col_ref:
    st.markdown("**Clean Reference Dataset**")
    st.caption(f"{len(ref_df):,} rows, {len(ref_df.columns)} columns")
    st.dataframe(ref_df, use_container_width=True, height=400)

st.divider()

# ── Combined SQL ──────────────────────────────────────────────────────────

st.subheader("Combined SQL Pipeline")
st.caption("All fixes chained into a single CTE query.")

cte_parts = []
for issue in issues:
    if not issue.sql_fix:
        continue
    sql_clean = issue.sql_fix.strip()
    if sql_clean.upper().startswith("SELECT"):
        cte_parts.append((issue.category, sql_clean))

if cte_parts:
    combined = "-- Combined Data Quality Fix Pipeline\n\n"
    prev = "raw_data"
    for i, (cat, sql) in enumerate(cte_parts):
        step = f"fix_{i+1}_{cat}"[:40]
        adjusted = sql.replace("raw_data", prev).rstrip(";")
        if i == 0:
            combined += f"WITH {step} AS (\n"
        else:
            combined += f"),\n{step} AS (\n"
        for line in adjusted.split("\n"):
            combined += f"    {line}\n"
        prev = step
    combined += f")\nSELECT * FROM {prev};"
    st.code(combined, language="sql")

st.divider()
st.caption(
    "Data Quality & SQL Repair Studio | "
    "Built with Python, Streamlit, DuckDB"
)
