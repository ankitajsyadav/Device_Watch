"""
Page 3: Manufacturers.

Firm-level analysis: top recallers, severity mix, repeat-offender detection,
and firm-level cycle time benchmarking.
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from src.data_loader import get_data
from src.queries import run_sql

st.set_page_config(page_title="Manufacturers · DeviceWatch", layout="wide")

df, con = get_data()
start = st.session_state.get("start")
end = st.session_state.get("end")

st.title("Manufacturers")
st.caption("Firm-level recall patterns and severity")

if not start or not end:
    st.info("Open the Home page first to set the date range.")
    st.stop()

start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)

top_n = st.slider("How many firms to show", 5, 50, 20, step=5)

top = run_sql(
    con, "top_manufacturers.sql",
    params=[start_ts, start_ts, end_ts, end_ts, top_n],
)
if top.empty:
    st.info("Not enough data to compute firm-level rollups for this window.")
    st.stop()

# --- Top firms by recall count, stacked by severity ------------------------
st.subheader("Recall count and severity mix")

melted = top.melt(
    id_vars=["recalling_firm"],
    value_vars=["class_i_count", "class_ii_count", "class_iii_count"],
    var_name="classification", value_name="count",
)
melted["classification"] = melted["classification"].map({
    "class_i_count": "Class I",
    "class_ii_count": "Class II",
    "class_iii_count": "Class III",
})
fig = px.bar(
    melted.sort_values("count", ascending=False),
    x="count", y="recalling_firm", color="classification",
    category_orders={
        "classification": ["Class I", "Class II", "Class III"],
        "recalling_firm": top["recalling_firm"].tolist()[::-1],
    },
    color_discrete_map={"Class I": "#d62728", "Class II": "#ff7f0e", "Class III": "#2ca02c"},
    orientation="h",
    labels={"recalling_firm": "", "count": "Recalls"},
)
fig.update_layout(height=max(360, 24 * top_n),
                  margin=dict(l=0, r=0, t=10, b=0), barmode="stack",
                  legend=dict(orientation="h", yanchor="bottom", y=1.02))
st.plotly_chart(fig, use_container_width=True)

# --- Repeat-offender table -------------------------------------------------
st.subheader("Detail")
st.dataframe(
    top.rename(columns={
        "recalling_firm": "Firm",
        "total_recalls": "Total",
        "class_i_count": "Class I",
        "class_ii_count": "Class II",
        "class_iii_count": "Class III",
        "avg_cycle_days": "Avg cycle (days)",
        "pct_class_i": "% Class I",
    }),
    hide_index=True, use_container_width=True,
)

# --- Risk view: avg cycle vs Class I share --------------------------------
st.subheader("Severity vs. resolution speed")
st.caption(
    "Bubble size = total recalls. Firms in the upper-right (high Class I share, "
    "slow cycle) merit closer attention."
)
scatter_df = top.dropna(subset=["avg_cycle_days"])
if not scatter_df.empty:
    fig = px.scatter(
        scatter_df,
        x="avg_cycle_days", y="pct_class_i",
        size="total_recalls", hover_name="recalling_firm",
        labels={
            "avg_cycle_days": "Avg cycle days (lower = faster)",
            "pct_class_i": "% Class I (higher = more severe)",
        },
    )
    fig.update_layout(height=400, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)
