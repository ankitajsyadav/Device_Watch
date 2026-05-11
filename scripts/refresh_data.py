"""
Fetch medical device enforcement (recall) records from openFDA.

Uses openFDA's bulk download endpoint rather than the search API. The
bulk endpoint serves a single zipped JSON containing every record --
faster, no rate limits, no query-parser edge cases, and one request
instead of dozens.

Pipeline:
    1. Hit api.fda.gov/download.json to find the current bulk URL
       (falling back to the documented URL if that's unreachable)
    2. Download the zip with progress logging
    3. Unzip and parse the JSON in memory
    4. Filter to the requested date range
    5. Write a parquet snapshot to data/device_enforcement.parquet

Usage:
    python scripts/refresh_data.py                  # default: last 5 years
    python scripts/refresh_data.py --years 10
    python scripts/refresh_data.py --since 2020-01-01
    python scripts/refresh_data.py --all            # full history (2004-present)

The script is idempotent and parameterized -- wrap it in Airflow/cron
without modification.
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import sys
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

# openFDA metadata endpoint lists current bulk-download URLs per dataset
METADATA_URL = "https://api.fda.gov/download.json"

# Documented fallback URL -- stable for years, but the metadata lookup
# above is the canonical way to discover the current location
FALLBACK_DOWNLOAD_URL = (
    "https://download.open.fda.gov/device/enforcement/"
    "device-enforcement-0001-of-0001.json.zip"
)

REQUEST_TIMEOUT = 60        # bulk file is ~10-20 MB, allow time on slow links
DOWNLOAD_CHUNK_SIZE = 65536

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_PATH = DATA_DIR / "device_enforcement.parquet"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("refresh_data")


# --- Discovery -------------------------------------------------------------
def discover_download_url() -> str:
    """Find the current bulk-download URL for device enforcement.

    Queries the openFDA metadata endpoint and returns the first partition
    URL for /device/enforcement. Falls back to the documented URL if the
    metadata lookup fails for any reason.
    """
    try:
        resp = requests.get(METADATA_URL, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        meta = resp.json()
        partitions = (
            meta.get("results", {})
                .get("device", {})
                .get("enforcement", {})
                .get("partitions", [])
        )
        if partitions and "file" in partitions[0]:
            url = partitions[0]["file"]
            log.info("discovered current bulk URL: %s", url)
            return url
    except Exception as e:
        log.warning("metadata lookup failed (%s); using documented URL", e)
    return FALLBACK_DOWNLOAD_URL


# --- Download --------------------------------------------------------------
def download_bytes(url: str) -> bytes:
    """Stream the zip to memory with progress logging. Returns raw bytes."""
    log.info("downloading %s", url)
    with requests.get(url, stream=True, timeout=REQUEST_TIMEOUT) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length") or 0)
        buf = io.BytesIO()
        downloaded = 0
        last_logged = 0
        for chunk in resp.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
            if not chunk:
                continue
            buf.write(chunk)
            downloaded += len(chunk)
            # log every ~2 MB so the user sees progress on slow links
            if downloaded - last_logged >= 2 * 1024 * 1024:
                last_logged = downloaded
                if total:
                    pct = downloaded / total * 100
                    log.info("  ...%5.1f MB / %.1f MB (%.0f%%)",
                             downloaded / 1_048_576, total / 1_048_576, pct)
                else:
                    log.info("  ...%5.1f MB downloaded", downloaded / 1_048_576)
        log.info("download complete -- %.1f MB", downloaded / 1_048_576)
        return buf.getvalue()


def extract_records(zip_bytes: bytes) -> list[dict]:
    """Open the zip in memory and return the `results` list from its JSON."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # The archive contains a single .json file
        json_names = [n for n in zf.namelist() if n.endswith(".json")]
        if not json_names:
            raise RuntimeError(f"no .json file in archive; got {zf.namelist()}")
        with zf.open(json_names[0]) as f:
            payload = json.load(f)
    results = payload.get("results", [])
    if not results:
        raise RuntimeError("archive contained no records under 'results'")
    log.info("parsed %d records from %s", len(results), json_names[0])
    return results


# --- Transform -------------------------------------------------------------
def to_dataframe(records: list[dict], since: str | None) -> pd.DataFrame:
    """Convert raw records to a DataFrame, optionally filtering by date."""
    df = pd.DataFrame(records)
    # The bulk file includes an `openfda` annotation block we don't use
    df = df.drop(columns=["openfda"], errors="ignore")

    if since:
        # openFDA dates are YYYYMMDD strings -- compare as strings to avoid
        # paying parse cost on the full ~30k-row dataset
        since_compact = since.replace("-", "")
        if "report_date" in df.columns:
            mask = df["report_date"].astype("string") >= since_compact
            kept = int(mask.sum())
            log.info("filtered to %d records on or after %s (dropped %d)",
                     kept, since, len(df) - kept)
            df = df[mask].reset_index(drop=True)
    return df


def write_snapshot(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False, compression="snappy")
    log.info("wrote %d rows to %s (%.1f MB)",
             len(df), path, path.stat().st_size / 1_048_576)


# --- Public entrypoint used by data_loader.py fallback ---------------------
def fetch_recalls(since: str | None = None) -> pd.DataFrame:
    """Programmatic entrypoint: download, parse, optionally filter, return df.

    Kept for the data_loader's fallback path so the app can populate itself
    on first run without requiring the CLI to have been invoked first.
    """
    url = discover_download_url()
    zip_bytes = download_bytes(url)
    records = extract_records(zip_bytes)
    return to_dataframe(records, since=since)


# --- CLI -------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--years", type=int, default=5,
                   help="how many years back from today to keep (default: 5)")
    g.add_argument("--since", type=str,
                   help="explicit start date, YYYY-MM-DD")
    g.add_argument("--all", action="store_true",
                   help="keep the full dataset (2004-present), no date filter")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH,
                        help=f"output parquet path (default: {OUTPUT_PATH})")
    parser.add_argument("--url", type=str, default=None,
                        help="override the bulk download URL (skips discovery)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.all:
        since = None
    elif args.since:
        since = args.since
    else:
        since = (datetime.utcnow() - timedelta(days=365 * args.years)).strftime("%Y-%m-%d")

    url = args.url or discover_download_url()
    zip_bytes = download_bytes(url)
    records = extract_records(zip_bytes)
    df = to_dataframe(records, since=since)
    write_snapshot(df, args.output)

    if not df.empty and "report_date" in df.columns:
        log.info("done -- coverage: %s to %s",
                 df["report_date"].min(), df["report_date"].max())
    return 0


if __name__ == "__main__":
    sys.exit(main())
