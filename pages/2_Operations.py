"""
Page 2: Operations.

Operational metrics: cycle time from initiation to termination, status
backlog of recalls still in flight, and geographic distribution.
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from src.data_loader import get_data
from src.queries import run_sql

st.set_page_config(page_title="Operations · DeviceWatch", layout="wide")

df, con = get_data()
start = st.session_state.get("start")
end = st.session_state.get("end")

st.title("Operations")
st.caption("How quickly are recalls resolved? Where are they happening?")

if not start or not end:
    st.info("Open the Home page first to set the date range.")
    st.stop()

start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)

# --- Cycle time table ------------------------------------------------------
st.subheader("Cycle time by classification")
st.caption("Days from recall initiation to termination, for terminated recalls only")

cycle = run_sql(
    con, "cycle_time.sql",
    params=[start_ts, start_ts, end_ts, end_ts],
)
if cycle.empty:
    st.info("No terminated recalls in this window yet.")
else:
    st.dataframe(
        cycle.rename(columns={
            "terminated_recalls": "Terminated",
            "avg_cycle_days": "Avg days",
            "median_cycle_days": "Median",
            "min_cycle_days": "Min",
            "max_cycle_days": "Max",
            "p90_cycle_days": "P90",
        }),
        hide_index=True, use_container_width=True,
    )

# --- Cycle time distribution histogram ------------------------------------
st.subheader("Cycle time distribution")

cycles_df = df[
    (df["recall_initiation_date"] >= start_ts)
    & (df["recall_initiation_date"] <= end_ts)
    & df["cycle_days"].notna()
]
if cycles_df.empty:
    st.info("No cycle data in this window.")
else:
    fig = px.histogram(
        cycles_df, x="cycle_days", color="classification",
        nbins=40,
        category_orders={"classification": ["Class I", "Class II", "Class III"]},
        color_discrete_map={"Class I": "#d62728", "Class II": "#ff7f0e", "Class III": "#2ca02c"},
        labels={"cycle_days": "Cycle days (initiation → termination)"},
        barmode="stack",
    )
    fig.update_layout(height=360, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig, use_container_width=True)

# --- Two columns: status + geography --------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("Status distribution")
    status = run_sql(
        con, "status_distribution.sql",
        params=[start_ts, start_ts, end_ts, end_ts],
    )
    fig = px.bar(
        status, x="status", y="recall_count",
        text="pct_of_total",
        color="status",
        labels={"status": "", "recall_count": "Recalls"},
    )
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Recalls in *Ongoing* or *Pending* status represent operational backlog.")

with right:
    st.subheader("Top 15 states (US recalling firms)")
    geo = run_sql(
        con, "geographic_distribution.sql",
        params=[start_ts, start_ts, end_ts, end_ts],
    ).head(15)
    fig = px.bar(
        geo.sort_values("recall_count"),
        x="recall_count", y="state",
        orientation="h",
        color="class_i_count",
        color_continuous_scale="Reds",
        labels={"recall_count": "Total recalls",
                "state": "", "class_i_count": "Class I"},
    )
    fig.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

# --- Quantity affected ----------------------------------------------------
st.subheader("Estimated product quantity affected")
window = df[
    (df["recall_initiation_date"] >= start_ts)
    & (df["recall_initiation_date"] <= end_ts)
]
qty_total = int(window["product_quantity_numeric"].fillna(0).sum())
qty_parsed = int(window["product_quantity_numeric"].notna().sum())
st.metric(
    f"{qty_total:,} units / boxes / cases (across {qty_parsed:,} recalls with parseable quantity)",
    value="",
)
st.caption(
    "openFDA reports `product_quantity` as free text in mixed units. The number above sums "
    "the leading integer of each recall's quantity field -- treat it as a rough volume proxy, "
    "not a precise unit count."
)
