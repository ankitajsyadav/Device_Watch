-- Monthly count of recalls, optionally filtered by date range and classification.
-- Parameters are bound via DuckDB's ? placeholder (set to NULL to skip a filter).
--
-- Used by:
--   * Home page -- headline monthly trend
--   * Recall Trends -- top chart
SELECT
    date_trunc('month', recall_initiation_date)        AS month,
    classification,
    COUNT(*)                                            AS recall_count
FROM recalls
WHERE recall_initiation_date IS NOT NULL
  AND (? IS NULL OR recall_initiation_date >= CAST(? AS DATE))
  AND (? IS NULL OR recall_initiation_date <= CAST(? AS DATE))
  AND (? IS NULL OR classification = ?)
GROUP BY 1, 2
ORDER BY 1, 2;
