"""
Run versioned SQL files against the in-memory DuckDB connection.

Every KPI in the app is defined as a parameterized .sql file under sql/.
This keeps the analytical logic out of Python -- the same SQL would run
unchanged against a Snowflake or BigQuery warehouse if the data layer
were swapped out.

Usage:
    df = run_sql(con, "monthly_recalls.sql", params=[start, start, end, end, None, None])
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

import duckdb
import pandas as pd

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


@lru_cache(maxsize=64)
def load_sql(filename: str) -> str:
    """Read a .sql file from sql/. Cached -- files are small and rarely change."""
    path = SQL_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"SQL file not found: {path}")
    return path.read_text(encoding="utf-8")


def run_sql(
    con: duckdb.DuckDBPyConnection,
    filename: str,
    params: Sequence[Any] | None = None,
) -> pd.DataFrame:
    """Execute the SQL file with optional positional parameters."""
    sql = load_sql(filename)
    if params is None:
        return con.execute(sql).fetchdf()
    return con.execute(sql, list(params)).fetchdf()


def list_sql_files() -> list[str]:
    """All SQL files available -- used by the Data Quality page to show lineage."""
    return sorted(p.name for p in SQL_DIR.glob("*.sql"))
