"""
Unit tests for the data validation module.

These tests construct minimal DataFrames in memory -- no openFDA API
calls, no parquet I/O. They run in well under a second and are suitable
for a pre-commit hook or CI step.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Allow the tests to import the src package without installing it
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.validation import (REQUIRED_COLUMNS, check_classification_domain,
                            check_data_freshness, check_no_null_keys,
                            check_recall_number_unique,
                            check_required_columns, check_row_count,
                            check_termination_after_initiation, run_all,
                            summarize)


def _minimal_df(**overrides) -> pd.DataFrame:
    """A small valid frame with all required columns. Overrides replace columns."""
    today = pd.Timestamp.now().normalize()
    base = {
        "recall_number": [f"Z-{i:06d}" for i in range(150)],
        "classification": ["Class II"] * 150,
        "status": ["Terminated"] * 150,
        "recalling_firm": ["Acme Medical Inc"] * 150,
        "product_description": ["Test device"] * 150,
        "reason_for_recall": ["Test reason"] * 150,
        "voluntary_mandated": ["Voluntary: Firm initiated"] * 150,
        "country": ["United States"] * 150,
        "state": ["CA"] * 150,
        "recall_initiation_date": [(today - pd.Timedelta(days=30)).strftime("%Y%m%d")] * 150,
        "report_date": [today.strftime("%Y%m%d")] * 150,
        "termination_date": [today.strftime("%Y%m%d")] * 150,
    }
    base.update(overrides)
    return pd.DataFrame(base)


# --- Schema --------------------------------------------------------------
def test_required_columns_pass():
    result = check_required_columns(_minimal_df())
    assert result.passed
    assert result.category == "schema"


def test_required_columns_fail_when_missing():
    df = _minimal_df().drop(columns=["classification"])
    result = check_required_columns(df)
    assert not result.passed
    assert "classification" in result.details["missing"]


def test_row_count_pass():
    assert check_row_count(_minimal_df()).passed


def test_row_count_fail_under_threshold():
    df = _minimal_df().head(10)
    result = check_row_count(df, min_rows=100)
    assert not result.passed


def test_recall_number_unique_detects_duplicates():
    df = _minimal_df()
    df.loc[1, "recall_number"] = df.loc[0, "recall_number"]
    result = check_recall_number_unique(df)
    assert not result.passed
    assert result.details["duplicates"] == 1
    assert result.severity == "warning"  # duplicates warn, don't fail


def test_no_null_keys_pass():
    assert check_no_null_keys(_minimal_df()).passed


def test_no_null_keys_fail_on_null_firm():
    df = _minimal_df()
    df.loc[0, "recalling_firm"] = None
    result = check_no_null_keys(df)
    assert not result.passed


# --- Domain --------------------------------------------------------------
def test_classification_domain_pass():
    assert check_classification_domain(_minimal_df()).passed


def test_classification_domain_detects_unknown():
    df = _minimal_df()
    df.loc[0, "classification"] = "Class IV"
    result = check_classification_domain(df)
    assert not result.passed
    assert "Class IV" in result.details["unknown"]


# --- Business -----------------------------------------------------------
def test_termination_after_initiation_pass():
    assert check_termination_after_initiation(_minimal_df()).passed


def test_termination_after_initiation_detects_inversion():
    df = _minimal_df()
    # set termination_date to before initiation_date
    df.loc[0, "termination_date"] = "20200101"
    df.loc[0, "recall_initiation_date"] = "20240101"
    result = check_termination_after_initiation(df)
    assert not result.passed
    assert result.details["violations"] == 1


def test_data_freshness_pass_when_recent():
    assert check_data_freshness(_minimal_df()).passed


def test_data_freshness_fail_when_stale():
    df = _minimal_df()
    df["report_date"] = "20200101"
    result = check_data_freshness(df, max_age_days=60)
    assert not result.passed


# --- Orchestration ------------------------------------------------------
def test_run_all_returns_one_result_per_check():
    results = run_all(_minimal_df())
    assert len(results) >= 5
    assert all(r.category in {"schema", "types", "domain", "business"} for r in results)


def test_summarize_counts_correctly():
    results = run_all(_minimal_df())
    summary = summarize(results)
    assert summary["total"] == len(results)
    assert summary["passed"] + summary["failed"] + summary["warned"] == len(results)
    assert 0 <= summary["pass_rate"] <= 100
