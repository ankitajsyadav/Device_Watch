"""
DeviceWatch -- Home page.

Top-line KPIs and a monthly trend across the selected date window.
Use the sidebar to filter what every page sees.
"""
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from src.data_loader import get_data
from src.kpis import (avg_cycle_days, class_i_count, ongoing_recalls,
                     total_recalls, yoy_change)
from src.queries import run_sql

st.set_page_config(
    page_title="DeviceWatch",
    page_icon="🩺",
    layout="wide",
)


# ---- Load data once for the session --------------------------------------
df, con = get_data()


# ---- Sidebar: filters shared across pages --------------------------------
def render_sidebar() -> tuple[date, date, str | None]:
    st.sidebar.title("Filters")
    st.sidebar.caption("Applied across all pages")

    # Default to last 3 years of available data
    min_date = df["recall_initiation_date"].min().date() if df["recall_initiation_date"].notna().any() else date(2020, 1, 1)
    max_date = df["recall_initiation_date"].max().date() if df["recall_initiation_date"].notna().any() else date.today()
    default_start = max(min_date, max_date - timedelta(days=365 * 3))

    start, end = st.sidebar.date_input(
        "Date range (recall initiation)",
        value=(default_start, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    classification = st.sidebar.selectbox(
        "Classification",
        options=["All", "Class I", "Class II", "Class III"],
    )
    cls = None if classification == "All" else classification

    st.sidebar.divider()
    st.sidebar.caption(
        f"Snapshot covers {min_date} to {max_date} \n\n"
        f"Refresh by running `python scripts/refresh_data.py`"
    )
    return start, end, cls


start, end, classification = render_sidebar()
# stash for other pages
st.session_state["start"] = start
st.session_state["end"] = end
st.session_state["classification"] = classification

# Window for KPI helpers
window_df = df[
    (df["recall_initiation_date"] >= pd.Timestamp(start))
    & (df["recall_initiation_date"] <= pd.Timestamp(end))
]
if classification:
    window_df = window_df[window_df["classification"] == classification]


# ---- Headline ------------------------------------------------------------
st.title("🩺 DeviceWatch")
st.markdown(
    "**Medical device recall analytics, powered by FDA's openFDA enforcement data.** "
    "This dashboard analyzes recall volume, severity, operational cycle times, and "
    "manufacturer-level patterns to surface quality and operational signals."
)

# ---- KPI row -------------------------------------------------------------
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Recalls", f"{total_recalls(window_df):,}")
col2.metric("Class I (severe)", f"{class_i_count(window_df):,}")
col3.metric("Ongoing", f"{ongoing_recalls(window_df):,}")
cycle = avg_cycle_days(window_df)
col4.metric("Avg cycle (days)", f"{cycle:.0f}" if cycle else "—")
yoy = yoy_change(df, end=pd.Timestamp(end))
col5.metric(
    "YoY change",
    f"{yoy:+.1f}%" if yoy is not None else "—",
    delta_color="inverse",  # more recalls is bad
)

st.divider()


# ---- Trend chart ---------------------------------------------------------
st.subheader("Monthly recall volume by classification")

params = [
    pd.Timestamp(start), pd.Timestamp(start),
    pd.Timestamp(end), pd.Timestamp(end),
    classification, classification,
]
monthly = run_sql(con, "monthly_recalls.sql", params=params)

if monthly.empty:
    st.info("No recalls match the current filters.")
else:
    fig = px.area(
        monthly,
        x="month",
        y="recall_count",
        color="classification",
        category_orders={"classification": ["Class I", "Class II", "Class III"]},
        color_discrete_map={"Class I": "#d62728", "Class II": "#ff7f0e", "Class III": "#2ca02c"},
        labels={"month": "Initiation month", "recall_count": "Recall count"},
    )
    fig.update_layout(
        height=380, margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)

# ---- Narrative -----------------------------------------------------------
with st.expander("How to read this dashboard"):
    st.markdown(
        """
        **Classifications** indicate hazard severity:
        - **Class I** — reasonable probability of serious adverse health consequences or death
        - **Class II** — temporary or medically reversible adverse health consequences
        - **Class III** — unlikely to cause adverse health consequences

        **Pages:**
        - **Recall Trends** — temporal patterns, classification mix, voluntary vs FDA-mandated
        - **Operations** — cycle time from initiation to termination, status backlog, geography
        - **Manufacturers** — firm-level recall counts, severity mix, repeat-offender detection
        - **Data Quality** — validation results on the underlying snapshot

        Every chart is computed by SQL run against an in-memory DuckDB table.
        The `.sql` files are versioned alongside the dashboard code.
        """
    )

st.caption(
    "Data source: [openFDA Device Enforcement API](https://open.fda.gov/apis/device/enforcement/) "
    "· Updates weekly · No PII"
)
