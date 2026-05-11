# 🩺 DeviceWatch — Medical Device Recall Analytics

> An interactive analytics dashboard for monitoring FDA medical device recalls — recall volume, severity, operational cycle times, and manufacturer-level patterns — built on the public openFDA dataset.

**🔗 [Live demo](https://YOUR-APP.streamlit.app)** · **[Source code](https://github.com/YOUR-USERNAME/devicewatch)**

> _Replace the two links above with your deployed Streamlit URL and GitHub repo URL._

---

## Overview

Medical device recalls are one of the clearest public signals of quality and operational risk in the healthcare-products industry. Every recall the FDA logs includes severity classification, root cause, distribution scope, and lifecycle dates — a rich, multi-dimensional dataset that's perfect for analytics.

I built **DeviceWatch** as an end-to-end analytics project: it ingests recall data from openFDA's bulk download endpoint, validates and transforms it, models it for SQL analysis, and surfaces the results through a four-page Streamlit dashboard. Every chart in the app is computed by a versioned SQL file run against an in-memory DuckDB table — the same SQL that would run unchanged against a real warehouse.

The goal was to demonstrate the full analyst-engineer workflow: **automated ingestion → data modeling → quality validation → SQL-driven KPIs → business-friendly visualization** — in a project small enough to fully understand in one read-through.

---

## What it shows

| Page              | Question it answers                                                          |
|-------------------|------------------------------------------------------------------------------|
| **Home**          | What's the current state of medical device recalls? Volume, severity, YoY change. |
| **Recall Trends** | How is recall volume and severity changing over time? Voluntary vs FDA-mandated mix. |
| **Operations**    | How long do recalls take to resolve? Where are they concentrated geographically? |
| **Manufacturers** | Which firms recall most? Most severely? Slowest to resolve?                  |
| **Data Quality**  | Can I trust the underlying data? What validation checks ran on it?           |

Every chart respects a global date range filter and (where applicable) a classification filter, both controlled from the sidebar.

---

## Tech stack

| Layer            | Tool                                  | Why                                                        |
|------------------|---------------------------------------|------------------------------------------------------------|
| Language         | Python 3.10+                          | Standard for analytics work                                |
| Analytical SQL   | DuckDB (embedded)                     | Real SQL without provisioning a warehouse                  |
| Transform        | pandas                                | Cleansing, type coercion, derived columns                  |
| Storage          | Parquet (snappy)                      | Columnar, compressed, portable                             |
| App              | Streamlit (multipage)                 | Fast to build, easy to deploy, clean UX                    |
| Charts           | Plotly                                | Interactive, rich, plays well with Streamlit               |
| Ingestion        | `requests` + `zipfile`                | openFDA bulk download, no rate limits                      |
| Tests            | pytest                                | Unit tests on the validation module (15 tests, <1s)        |

---

## Architecture

```
                    ┌────────────────────────────────────────┐
                    │  openFDA bulk download endpoint        │
                    │  download.open.fda.gov/.../*.json.zip  │
                    └──────────────┬─────────────────────────┘
                                   │ one zip, all records
                                   ▼
                    ┌────────────────────────────────────────┐
                    │  scripts/refresh_data.py               │  ← ingestion
                    │  - URL discovery via metadata endpoint │
                    │  - streamed download w/ progress       │
                    │  - in-memory unzip + JSON parse        │
                    │  - date filter → parquet               │
                    └──────────────┬─────────────────────────┘
                                   ▼
                    ┌────────────────────────────────────────┐
                    │  data/device_enforcement.parquet       │  ← snapshot
                    └──────────────┬─────────────────────────┘
                                   ▼
                    ┌────────────────────────────────────────┐
                    │  src/data_loader.py                    │  ← transform
                    │  - parquet → pandas                    │
                    │  - cleansing (dates, qty, strings)     │
                    │  - DuckDB registration                 │
                    └──────────────┬─────────────────────────┘
                                   ▼
            ┌───────────────────┐  │  ┌───────────────────────┐
            │  src/validation.py│  │  │  sql/*.sql            │
            │  - 9 checks       │  │  │  - parameterized      │  ← analytics
            │  - 4 categories   │◀─┴─▶│  - DuckDB SQL         │
            └─────────┬─────────┘     └──────────┬────────────┘
                      ▼                          ▼
                    ┌────────────────────────────────────────┐
                    │  Streamlit pages                       │  ← presentation
                    │   Home · Trends · Ops · Mfrs · DQ      │
                    └────────────────────────────────────────┘
```

### Design choices worth calling out

- **Bulk download over the search API.** openFDA exposes both a paginated search API and a single bulk-export endpoint. I went with bulk: one network call, no rate limits, no query-parser edge cases, and well under a second to download. The search API would have meant 20+ paginated calls and brittle URL encoding.
- **DuckDB instead of pandas group-bys.** Every KPI lives in a real `.sql` file under `sql/`. That keeps the analytical logic out of Python, versionable in isolation, and portable — the same SQL would run unchanged against Snowflake or BigQuery.
- **Validation as a visible page.** Data quality isn't a hidden background check — it's its own dashboard page. A reviewer always knows what the analysis is built on.
- **Single-file cleansing.** The dataset is small enough (~20k recalls over 5 years) that a layered medallion model would be overkill. Cleansing is consolidated in `data_loader.py` with documented steps.

---

## Local setup

```bash
git clone https://github.com/YOUR-USERNAME/devicewatch.git
cd devicewatch

python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

pip install -r requirements.txt
python scripts/refresh_data.py       # downloads bulk file from openFDA (~15-30s)
streamlit run streamlit_app.py
```

The data refresh script supports a few options:

```bash
python scripts/refresh_data.py                    # default: last 5 years
python scripts/refresh_data.py --years 10
python scripts/refresh_data.py --since 2018-01-01
python scripts/refresh_data.py --all              # full history (2004-present)
```

To run the test suite:

```bash
pytest tests/ -v
```

---

## Project structure

```
devicewatch/
├── streamlit_app.py              # Home page
├── pages/
│   ├── 1_Recall_Trends.py
│   ├── 2_Operations.py
│   ├── 3_Manufacturers.py
│   └── 4_Data_Quality.py
├── src/
│   ├── data_loader.py            # parquet → pandas → DuckDB
│   ├── validation.py             # 9 quality checks across 4 categories
│   ├── queries.py                # SQL loader/executor
│   └── kpis.py                   # headline-metric helpers
├── sql/                          # one file per KPI
│   ├── monthly_recalls.sql
│   ├── classification_mix.sql
│   ├── cycle_time.sql
│   ├── top_manufacturers.sql
│   ├── status_distribution.sql
│   ├── geographic_distribution.sql
│   └── voluntary_vs_mandated.sql
├── scripts/
│   └── refresh_data.py           # openFDA bulk ingestion
├── tests/
│   └── test_validation.py        # 15 unit tests, sub-second
├── docs/
│   └── kpi_definitions.md        # business-language KPI specs
├── data/
│   └── device_enforcement.parquet
├── .streamlit/config.toml
├── requirements.txt
└── README.md
```

---

## Scaling considerations

What's deliberately not built here, and how it would scale in a production environment:

- **Orchestration.** `scripts/refresh_data.py` is a single idempotent function with a CLI. Wrapping it in an Airflow DAG (or Prefect, Dagster) is one config file — fetch → validate → archive previous snapshot → publish.
- **Spark.** Pandas handles ~30k records trivially. If the dataset grew to tens of millions of rows, the cleansing in `data_loader.py` would migrate to PySpark; the SQL layer is portable as-is.
- **Storage.** Local parquet works for this scale. In production, the same parquet would land in S3/GCS, and DuckDB can read it via `read_parquet('s3://...')` — or the SQL could be repointed at a warehouse with zero schema changes.
- **Data quality tooling.** The custom validation module covers the basics with clear category grouping. Great Expectations or Soda Core would give versioned suites, data docs, and alerting if this needed to graduate to a production data product.
- **Lineage & catalog.** A handful of versioned `.sql` files is sufficient at this scale. dbt would be the next step if the KPI count grew — with `.yml` files for column-level lineage and assertion-style tests.

---

## Data source

- **Dataset:** [openFDA Device Enforcement](https://open.fda.gov/apis/device/enforcement/) — the FDA's Recall Enterprise System (RES), publicly available, no API key required, updated weekly.
- **Coverage:** 2004 to present.
- **License:** [openFDA terms of service](https://open.fda.gov/terms/). The dataset contains no PII.

> ⚠️ This dashboard is not a clinical or regulatory tool. Recall data should not be used to make medical decisions — see openFDA's disclaimer.

---

## About

Built by **Ankita Yadav** as a portfolio project to demonstrate a full analyst-engineer workflow on a real public dataset — from ingestion to dashboard.

Questions or feedback are welcome via GitHub Issues.
