"""
Headline KPIs used across pages. Each function takes the cleansed DataFrame
(plus optional date filters) and returns a single scalar.

Kept lightweight on purpose -- complex aggregations live in versioned SQL
under sql/, where they can be reviewed and tested independently.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd


def _within_window(
    df: pd.DataFrame,
    start: datetime | None,
    end: datetime | None,
    date_col: str = "recall_initiation_date",
) -> pd.DataFrame:
    mask = df[date_col].notna()
    if start is not None:
        mask &= df[date_col] >= pd.Timestamp(start)
    if end is not None:
        mask &= df[date_col] <= pd.Timestamp(end)
    return df[mask]


def total_recalls(df: pd.DataFrame, start=None, end=None) -> int:
    return len(_within_window(df, start, end))


def class_i_count(df: pd.DataFrame, start=None, end=None) -> int:
    window = _within_window(df, start, end)
    return int((window["classification"] == "Class I").sum())


def ongoing_recalls(df: pd.DataFrame, start=None, end=None) -> int:
    """Recalls whose status is still active (not Terminated/Completed)."""
    window = _within_window(df, start, end)
    active = window["status"].isin(["Ongoing", "Pending"])
    return int(active.sum())


def avg_cycle_days(df: pd.DataFrame, start=None, end=None) -> float | None:
    """Mean days from initiation to termination, for terminated recalls only."""
    window = _within_window(df, start, end)
    cycles = window["cycle_days"].dropna()
    if cycles.empty:
        return None
    return round(float(cycles.mean()), 1)


def total_quantity_affected(df: pd.DataFrame, start=None, end=None) -> int:
    """Sum of parsed product_quantity_numeric across the window.

    Note: openFDA quantities are reported in inconsistent units
    (boxes, units, cases) -- treat the absolute number as a rough volume
    proxy rather than a precise unit count.
    """
    window = _within_window(df, start, end)
    return int(window["product_quantity_numeric"].fillna(0).sum())


def yoy_change(df: pd.DataFrame, end: datetime | None = None) -> float | None:
    """Year-over-year % change in trailing 12-month recall volume."""
    end = end or pd.Timestamp.now()
    current_start = end - timedelta(days=365)
    prior_start = end - timedelta(days=730)
    prior_end = current_start
    current = total_recalls(df, current_start, end)
    prior = total_recalls(df, prior_start, prior_end)
    if prior == 0:
        return None
    return round((current - prior) / prior * 100, 1)
