"""
Page 1: Recall Trends.

Temporal patterns, classification mix, voluntary vs FDA-mandated split,
and a small year-over-year comparison.
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from src.data_loader import get_data
from src.queries import run_sql

st.set_page_config(page_title="Recall Trends · DeviceWatch", layout="wide")

df, con = get_data()
start = st.session_state.get("start")
end = st.session_state.get("end")
classification = st.session_state.get("classification")

st.title("Recall Trends")
st.caption("Temporal patterns in recall volume and severity")

if not start or not end:
    st.info("Open the Home page first to set the date range.")
    st.stop()

start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)

# --- Monthly trend (all classifications regardless of sidebar filter, so the
#     user can see the mix visually) -----------------------------------------
monthly = run_sql(
    con, "monthly_recalls.sql",
    params=[start_ts, start_ts, end_ts, end_ts, None, None],
)
if monthly.empty:
    st.info("No data for this window.")
    st.stop()

st.subheader("Monthly volume by classification")
fig = px.bar(
    monthly,
    x="month", y="recall_count", color="classification",
    category_orders={"classification": ["Class I", "Class II", "Class III"]},
    color_discrete_map={"Class I": "#d62728", "Class II": "#ff7f0e", "Class III": "#2ca02c"},
    labels={"month": "Initiation month", "recall_count": "Recalls"},
)
fig.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=0), barmode="stack",
                  legend=dict(orientation="h", yanchor="bottom", y=1.02))
st.plotly_chart(fig, use_container_width=True)

# --- Two-column row: classification mix + voluntary vs mandated -----------
left, right = st.columns(2)

with left:
    st.subheader("Classification mix")
    mix = run_sql(
        con, "classification_mix.sql",
        params=[start_ts, start_ts, end_ts, end_ts],
    )
    fig = px.pie(
        mix, names="classification", values="recall_count",
        color="classification",
        color_discrete_map={"Class I": "#d62728", "Class II": "#ff7f0e", "Class III": "#2ca02c"},
        hole=0.55,
    )
    fig.update_traces(textposition="outside", textinfo="label+percent")
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(mix, hide_index=True, use_container_width=True)

with right:
    st.subheader("Voluntary vs FDA-mandated")
    vm = run_sql(
        con, "voluntary_vs_mandated.sql",
        params=[start_ts, start_ts, end_ts, end_ts],
    )
    fig = px.bar(
        vm, x="initiation_type", y="recall_count",
        text="pct_of_total", color="initiation_type",
        labels={"initiation_type": "", "recall_count": "Recalls"},
    )
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("The vast majority of recalls are firm-initiated. A rising mandated share is worth investigating.")

# --- YoY view --------------------------------------------------------------
st.subheader("Year-over-year, by month")
monthly["year"] = monthly["month"].dt.year
monthly["month_of_year"] = monthly["month"].dt.month
yoy = monthly.groupby(["year", "month_of_year"], as_index=False)["recall_count"].sum()
yoy["month_name"] = pd.to_datetime(yoy["month_of_year"], format="%m").dt.strftime("%b")
fig = px.line(
    yoy.sort_values(["year", "month_of_year"]),
    x="month_name", y="recall_count", color="year",
    markers=True, labels={"month_name": "Month", "recall_count": "Recalls"},
    category_orders={"month_name": ["Jan","Feb","Mar","Apr","May","Jun",
                                    "Jul","Aug","Sep","Oct","Nov","Dec"]},
)
fig.update_layout(height=360, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig, use_container_width=True)
