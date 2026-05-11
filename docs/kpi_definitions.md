# KPI definitions

Each KPI on the dashboard is computed by SQL in `sql/` against the
in-memory DuckDB table `recalls`. This document defines them in
business language so a non-technical reviewer can read the dashboard
without ambiguity.

---

## Headline KPIs (Home page)

### Total Recalls
Count of distinct recall events with a non-null `recall_initiation_date`
within the selected date window.

### Class I (severe)
Count of recalls where `classification = 'Class I'`. Class I recalls are
those where there is a reasonable probability that use of the product
will cause serious adverse health consequences or death.

### Ongoing
Count of recalls with `status IN ('Ongoing', 'Pending')`. Represents
operational backlog — recalls that have not yet been completed or
terminated.

### Avg cycle (days)
Mean of `termination_date - recall_initiation_date`, in days, computed
only over recalls that have actually been terminated. Cycles greater
than 10 years or negative are excluded as data errors.

### YoY change
Trailing 12-month recall volume vs the prior 12 months, expressed as a
percentage. A positive value means recall volume is rising
year-over-year. Computed from the end of the selected date window.

---

## Trend KPIs (Recall Trends page)

### Monthly volume
Recalls grouped by `date_trunc('month', recall_initiation_date)`,
broken out by classification.

### Classification mix
Share of total recalls by class, for the selected window. Useful as a
quality bellwether — a rising Class I share indicates more severe events.

### Voluntary vs FDA-mandated
Share of recalls where `voluntary_mandated` indicates a firm-initiated
recall vs an FDA-mandated one. The vast majority (typically >90%) are
voluntary; rising mandated share is worth investigating.

---

## Operations KPIs (Operations page)

### Cycle time (per classification)
Avg, median, P90, min, and max of `cycle_days` per classification.
Class I recalls do not necessarily resolve faster than lower-class ones
in practice — surfacing this is the point.

### Cycle time distribution
Histogram of cycle days bucketed across all terminated recalls in the
window, stacked by classification.

### Status distribution
Count and share of recalls per `status` value (Ongoing, Completed,
Terminated, Pending, Unknown). Ongoing/Pending = active backlog.

### Geographic distribution
Recall count by US state (of the recalling firm), with Class I count
overlaid as color intensity. Non-US firms are excluded from this view.

### Estimated product quantity affected
Sum of the parsed leading integer from each recall's `product_quantity`
field. Treat as a rough order-of-magnitude proxy — openFDA reports
quantities in mixed units (boxes, units, cases, lots) and many entries
are non-numeric ("Undetermined", "Unknown").

---

## Manufacturer KPIs (Manufacturers page)

### Top firms by total recalls
`recalling_firm` ranked by recall count in the selected window. Firms
with fewer than 2 recalls are excluded to focus on repeat-recallers.

### Severity mix per firm
Breakdown of each firm's recalls into Class I / II / III counts and
percentages. The `% Class I` column highlights firms whose recalls
tend to be more serious.

### Average cycle time per firm
Mean cycle days for the firm's terminated recalls. Combined with
severity mix on the scatter view: upper-right quadrant (high Class I
share, slow cycle) is the operational risk zone.

---

## Data quality KPIs (Data Quality page)

### Pass rate
`passed / total * 100`. Computed every app load; checks are listed in
`src/validation.py`.

### Categories
- **schema** — required columns present, row count sufficient,
  recall_number uniqueness, no nulls in key fields
- **types** — dates parse cleanly
- **domain** — classification and status values match known sets
- **business** — termination_date ≥ initiation_date, data freshness
  (latest record within 60 days of today)

### Severity
- **error** — analysis cannot be trusted; surfaces as red FAIL
- **warning** — analysis can proceed but the issue is worth reviewing;
  surfaces as yellow WARN
