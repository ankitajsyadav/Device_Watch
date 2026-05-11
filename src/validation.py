"""
Data quality validation for the openFDA device enforcement snapshot.

Each rule is a pure function: (df) -> CheckResult. Rules are grouped into
four categories so the dashboard can summarize pass/fail by category:

    schema    - expected columns present, no unexpected nulls in key fields
    types     - parseable dates, parseable integer quantities
    domain    - categorical values fall in known sets (e.g. classification)
    business  - logical invariants (termination_date >= initiation_date, etc.)

Run validation on every app load. Cheap (~milliseconds for tens of thousands
of rows) and gives the dashboard a real Data Quality page rather than a
decorative one.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

# --- Schema contract -------------------------------------------------------
# Fields the rest of the app depends on. If openFDA renames or removes one,
# the schema check fails fast and the page shows exactly what's missing.
REQUIRED_COLUMNS: list[str] = [
    "recall_number",
    "classification",
    "status",
    "recalling_firm",
    "product_description",
    "reason_for_recall",
    "voluntary_mandated",
    "country",
    "state",
    "recall_initiation_date",
    "report_date",
]

KNOWN_CLASSIFICATIONS = {"Class I", "Class II", "Class III"}
KNOWN_STATUSES = {"Ongoing", "Completed", "Terminated", "Pending"}


# --- Result type -----------------------------------------------------------
@dataclass
class CheckResult:
    name: str
    category: str           # schema | types | domain | business
    passed: bool
    severity: str           # error | warning
    message: str
    details: dict | None = None

    def to_row(self) -> dict:
        return {
            "check": self.name,
            "category": self.category,
            "status": "PASS" if self.passed else ("WARN" if self.severity == "warning" else "FAIL"),
            "severity": self.severity,
            "message": self.message,
        }


CheckFn = Callable[[pd.DataFrame], CheckResult]


# --- Individual checks -----------------------------------------------------
def check_required_columns(df: pd.DataFrame) -> CheckResult:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    return CheckResult(
        name="required_columns_present",
        category="schema",
        passed=len(missing) == 0,
        severity="error",
        message="all required columns present" if not missing
                else f"missing columns: {missing}",
        details={"missing": missing},
    )


def check_row_count(df: pd.DataFrame, min_rows: int = 100) -> CheckResult:
    n = len(df)
    return CheckResult(
        name="minimum_row_count",
        category="schema",
        passed=n >= min_rows,
        severity="error",
        message=f"{n:,} rows (minimum {min_rows:,})",
        details={"row_count": n},
    )


def check_recall_number_unique(df: pd.DataFrame) -> CheckResult:
    if "recall_number" not in df.columns:
        return CheckResult("recall_number_unique", "schema", False, "error",
                           "recall_number column missing")
    dupes = df["recall_number"].duplicated().sum()
    return CheckResult(
        name="recall_number_unique",
        category="schema",
        passed=dupes == 0,
        severity="warning",   # openFDA occasionally has dupes; warn don't fail
        message=f"{dupes} duplicate recall_numbers" if dupes else "all recall_numbers unique",
        details={"duplicates": int(dupes)},
    )


def check_no_null_keys(df: pd.DataFrame) -> CheckResult:
    """Critical fields used as join/group keys should never be null."""
    key_fields = ["recall_number", "classification", "recalling_firm"]
    present = [c for c in key_fields if c in df.columns]
    nulls = {c: int(df[c].isna().sum()) for c in present}
    failing = {c: n for c, n in nulls.items() if n > 0}
    return CheckResult(
        name="no_null_key_fields",
        category="schema",
        passed=len(failing) == 0,
        severity="error",
        message="no nulls in key fields" if not failing
                else f"nulls found: {failing}",
        details=nulls,
    )


def check_parseable_dates(df: pd.DataFrame) -> CheckResult:
    """openFDA dates arrive as YYYYMMDD strings -- ensure they parse."""
    date_cols = ["recall_initiation_date", "report_date", "center_classification_date",
                 "termination_date"]
    present = [c for c in date_cols if c in df.columns]
    bad = {}
    for c in present:
        parsed = pd.to_datetime(df[c], format="%Y%m%d", errors="coerce")
        # exclude rows where the original value was already null/empty
        original_present = df[c].notna() & (df[c].astype(str).str.len() > 0)
        unparseable = (parsed.isna() & original_present).sum()
        if unparseable > 0:
            bad[c] = int(unparseable)
    return CheckResult(
        name="dates_parseable",
        category="types",
        passed=len(bad) == 0,
        severity="warning",
        message="all dates parse cleanly" if not bad
                else f"unparseable values: {bad}",
        details=bad,
    )


def check_classification_domain(df: pd.DataFrame) -> CheckResult:
    if "classification" not in df.columns:
        return CheckResult("classification_in_known_set", "domain", False, "error",
                           "classification column missing")
    observed = set(df["classification"].dropna().unique())
    unknown = observed - KNOWN_CLASSIFICATIONS
    return CheckResult(
        name="classification_in_known_set",
        category="domain",
        passed=len(unknown) == 0,
        severity="warning",
        message="all classifications recognized" if not unknown
                else f"unexpected values: {sorted(unknown)}",
        details={"observed": sorted(observed), "unknown": sorted(unknown)},
    )


def check_status_domain(df: pd.DataFrame) -> CheckResult:
    if "status" not in df.columns:
        return CheckResult("status_in_known_set", "domain", False, "error",
                           "status column missing")
    observed = set(df["status"].dropna().unique())
    unknown = observed - KNOWN_STATUSES
    return CheckResult(
        name="status_in_known_set",
        category="domain",
        passed=len(unknown) == 0,
        severity="warning",
        message="all statuses recognized" if not unknown
                else f"unexpected values: {sorted(unknown)}",
        details={"observed": sorted(observed), "unknown": sorted(unknown)},
    )


def check_termination_after_initiation(df: pd.DataFrame) -> CheckResult:
    """Business rule: termination_date must be on or after recall_initiation_date."""
    needed = {"recall_initiation_date", "termination_date"}
    if not needed.issubset(df.columns):
        return CheckResult("termination_after_initiation", "business", False, "error",
                           "required date columns missing")
    init = pd.to_datetime(df["recall_initiation_date"], format="%Y%m%d", errors="coerce")
    term = pd.to_datetime(df["termination_date"], format="%Y%m%d", errors="coerce")
    both = init.notna() & term.notna()
    violations = int((both & (term < init)).sum())
    return CheckResult(
        name="termination_after_initiation",
        category="business",
        passed=violations == 0,
        severity="warning",
        message="no inverted recall lifecycles"
                if violations == 0 else f"{violations} records with termination_date < initiation_date",
        details={"violations": violations},
    )


def check_data_freshness(df: pd.DataFrame, max_age_days: int = 60) -> CheckResult:
    """The latest report_date should not be older than max_age_days.

    openFDA refreshes weekly, so anything older than ~60 days suggests
    the snapshot is stale and needs a refresh.
    """
    if "report_date" not in df.columns:
        return CheckResult("data_freshness", "business", False, "error",
                           "report_date missing")
    parsed = pd.to_datetime(df["report_date"], format="%Y%m%d", errors="coerce")
    if parsed.notna().sum() == 0:
        return CheckResult("data_freshness", "business", False, "warning",
                           "no parseable report_dates")
    latest = parsed.max()
    age_days = (pd.Timestamp.now() - latest).days
    return CheckResult(
        name="data_freshness",
        category="business",
        passed=age_days <= max_age_days,
        severity="warning",
        message=f"latest record is {age_days} days old (threshold: {max_age_days})",
        details={"latest_report_date": str(latest.date()), "age_days": age_days},
    )


# --- Orchestrator ----------------------------------------------------------
CHECKS: list[CheckFn] = [
    check_required_columns,
    check_row_count,
    check_recall_number_unique,
    check_no_null_keys,
    check_parseable_dates,
    check_classification_domain,
    check_status_domain,
    check_termination_after_initiation,
    check_data_freshness,
]


def run_all(df: pd.DataFrame) -> list[CheckResult]:
    """Run every check and return the list of results."""
    return [check(df) for check in CHECKS]


def summarize(results: list[CheckResult]) -> dict:
    """Compact summary for the dashboard header."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed and r.severity == "error")
    warned = sum(1 for r in results if not r.passed and r.severity == "warning")
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "warned": warned,
        "pass_rate": round(passed / total * 100, 1) if total else 0.0,
    }
