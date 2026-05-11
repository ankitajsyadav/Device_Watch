"""
Data loader: reads the openFDA snapshot, applies cleansing and type
coercion, and registers the result as a DuckDB table so SQL queries can
run against it.

The loader is wrapped in @st.cache_data so the parquet is read and
cleansed exactly once per session.

If no parquet exists locally, the loader will fetch a small recent
sample directly from the API. This keeps the Streamlit Cloud demo
working out of the box without committing a large data file to the repo
-- though running `python scripts/refresh_data.py` locally and committing
the parquet gives a faster, more comprehensive experience.
"""
from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = PROJECT_ROOT / "data" / "device_enforcement.parquet"

log = logging.getLogger(__name__)

# These are the columns the rest of the app reads. If openFDA returns
# additional columns we keep them, but anything missing is created as null
# so downstream SQL doesn't blow up.
EXPECTED_COLUMNS = [
    "recall_number", "event_id", "status", "classification",
    "product_type", "product_description", "product_code", "product_quantity",
    "reason_for_recall", "code_info", "more_code_info",
    "recalling_firm", "address_1", "address_2", "city", "state", "country",
    "distribution_pattern", "voluntary_mandated", "initial_firm_notification",
    "recall_initiation_date", "report_date", "center_classification_date",
    "termination_date",
]

DATE_COLUMNS = [
    "recall_initiation_date", "report_date",
    "center_classification_date", "termination_date",
]


# --- Cleansing -------------------------------------------------------------
def _coerce_dates(df: pd.DataFrame) -> pd.DataFrame:
    """openFDA serves dates as YYYYMMDD strings -- parse to real datetimes."""
    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format="%Y%m%d", errors="coerce")
    return df


def _coerce_quantity(df: pd.DataFrame) -> pd.DataFrame:
    """product_quantity is free-text in the source ('500 boxes', '12,000 units',
    'undetermined'). Extract the leading integer where possible so we can sum
    it; keep the original string for display.
    """
    if "product_quantity" not in df.columns:
        df["product_quantity_numeric"] = pd.NA
        return df
    df["product_quantity_numeric"] = (
        df["product_quantity"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.extract(r"(\d+)", expand=False)
        .pipe(pd.to_numeric, errors="coerce")
    )
    return df


def _normalize_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Trim whitespace; uppercase state codes; title-case firm names for display."""
    for col in ["classification", "status", "voluntary_mandated", "country"]:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()
    if "state" in df.columns:
        df["state"] = df["state"].astype("string").str.strip().str.upper()
    return df


def _derive_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add columns that several pages need."""
    if "recall_initiation_date" in df.columns:
        df["initiation_year"] = df["recall_initiation_date"].dt.year
        df["initiation_month"] = df["recall_initiation_date"].dt.to_period("M").dt.to_timestamp()
    if {"termination_date", "recall_initiation_date"}.issubset(df.columns):
        df["cycle_days"] = (
            df["termination_date"] - df["recall_initiation_date"]
        ).dt.days
        # ignore obviously bad cycles (negative or > 10 years)
        df.loc[(df["cycle_days"] < 0) | (df["cycle_days"] > 3650), "cycle_days"] = pd.NA
    return df


def cleanse(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all cleansing steps. Pure -- safe to memoize."""
    # Add any expected columns that are missing so the rest of the app
    # doesn't crash on a partial schema
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = _coerce_dates(df)
    df = _coerce_quantity(df)
    df = _normalize_strings(df)
    df = _derive_columns(df)
    return df


# --- Snapshot acquisition --------------------------------------------------
def _fetch_fallback_sample() -> pd.DataFrame:
    """Pull a recent sample directly from openFDA when no parquet exists.

    Kept small (~3000 records) so cold-start on Streamlit Cloud is fast.
    For a full historical view, run `python scripts/refresh_data.py` and
    commit the parquet.
    """
    # Imported here so the heavy network dep isn't loaded unless needed
    from scripts.refresh_data import fetch_recalls
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=730)).strftime("%Y-%m-%d")  # 2 years
    log.info("no local snapshot found; fetching last 2 years from openFDA")
    return fetch_recalls(since)


def load_raw() -> pd.DataFrame:
    """Read raw records from local parquet, falling back to API fetch."""
    if SNAPSHOT_PATH.exists():
        log.info("loading snapshot from %s", SNAPSHOT_PATH)
        return pd.read_parquet(SNAPSHOT_PATH)
    log.warning("snapshot not found at %s -- falling back to API fetch", SNAPSHOT_PATH)
    df = _fetch_fallback_sample()
    # write so subsequent loads are fast
    try:
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(SNAPSHOT_PATH, index=False, compression="snappy")
    except Exception as e:
        log.warning("could not write fallback snapshot: %s", e)
    return df


def load_clean() -> pd.DataFrame:
    """Public entrypoint: returns the cleansed DataFrame ready for analysis."""
    return cleanse(load_raw())


# --- DuckDB integration ----------------------------------------------------
def build_duckdb(df: pd.DataFrame) -> duckdb.DuckDBPyConnection:
    """Register the cleansed DataFrame as a DuckDB table named `recalls`.

    Using DuckDB rather than running pandas group-bys directly gives us
    real SQL in versioned .sql files -- the same SQL we'd run against a
    warehouse like Snowflake or BigQuery.
    """
    con = duckdb.connect(":memory:")
    con.register("recalls", df)
    return con


# --- Streamlit wrapper -----------------------------------------------------
# Streamlit-aware cached version. Streamlit isn't a hard dep of this module
# (so unit tests don't need it); the import is local.
def get_data():
    """Cached loader for use inside the Streamlit app.

    Returns:
        (df, con) tuple -- cleansed DataFrame and a DuckDB connection with
        the `recalls` table registered.
    """
    import streamlit as st

    @st.cache_data(show_spinner="Loading FDA recall data...")
    def _cached_df() -> pd.DataFrame:
        return load_clean()

    df = _cached_df()
    con = build_duckdb(df)  # DuckDB conn itself isn't cacheable across sessions
    return df, con
