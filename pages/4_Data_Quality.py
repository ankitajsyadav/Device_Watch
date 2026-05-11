"""
Page 4: Data Quality.

Surfaces the validation checks run on every app load. Lets a reviewer see
exactly what the analysis is built on -- categorized PASS/WARN/FAIL with
human-readable messages.
"""
import pandas as pd
import streamlit as st

from src.data_loader import SNAPSHOT_PATH, get_data
from src.queries import list_sql_files
from src.validation import REQUIRED_COLUMNS, run_all, summarize

st.set_page_config(page_title="Data Quality · DeviceWatch", layout="wide")

df, _ = get_data()

st.title("Data Quality")
st.caption("Every check that runs on the snapshot before any KPI is shown")

# --- Summary row ----------------------------------------------------------
results = run_all(df)
summary = summarize(results)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Checks run", summary["total"])
c2.metric("Passed", summary["passed"])
c3.metric("Warnings", summary["warned"])
c4.metric("Failures", summary["failed"])
c5.metric("Pass rate", f"{summary['pass_rate']}%")

if summary["failed"] > 0:
    st.error("One or more error-severity checks failed. KPIs may be unreliable.")
elif summary["warned"] > 0:
    st.warning("Some warnings -- analysis can proceed but review the details below.")
else:
    st.success("All checks passed.")

# --- Results table --------------------------------------------------------
st.subheader("Check results")
results_df = pd.DataFrame([r.to_row() for r in results])
# group by category for readability
for cat in ["schema", "types", "domain", "business"]:
    sub = results_df[results_df["category"] == cat]
    if sub.empty:
        continue
    st.markdown(f"**{cat.title()}**")
    st.dataframe(
        sub[["check", "status", "severity", "message"]],
        hide_index=True, use_container_width=True,
    )

# --- Snapshot info --------------------------------------------------------
st.divider()
left, right = st.columns(2)

with left:
    st.subheader("Snapshot")
    info = {
        "Source": "[openFDA Device Enforcement API](https://open.fda.gov/apis/device/enforcement/)",
        "Local path": f"`{SNAPSHOT_PATH.name}`",
        "Rows": f"{len(df):,}",
        "Columns": len(df.columns),
        "Earliest record": str(df["recall_initiation_date"].min().date())
                            if df["recall_initiation_date"].notna().any() else "—",
        "Latest record": str(df["recall_initiation_date"].max().date())
                          if df["recall_initiation_date"].notna().any() else "—",
    }
    st.write(pd.Series(info))

with right:
    st.subheader("Required schema")
    st.caption("Columns the app depends on")
    present = [(c, "✓" if c in df.columns else "✗") for c in REQUIRED_COLUMNS]
    st.dataframe(
        pd.DataFrame(present, columns=["Column", "Present"]),
        hide_index=True, use_container_width=True,
    )

# --- SQL lineage ----------------------------------------------------------
st.divider()
st.subheader("SQL files driving the KPIs")
st.caption("Every chart on every page is computed by one of these files")
st.dataframe(
    pd.DataFrame({"file": list_sql_files()}),
    hide_index=True, use_container_width=True,
)
