-- Cycle time = days from recall initiation to termination.
-- Returns per-classification summary statistics for completed recalls only.
SELECT
    classification,
    COUNT(*)                                  AS terminated_recalls,
    ROUND(AVG(cycle_days), 1)                 AS avg_cycle_days,
    ROUND(MEDIAN(cycle_days), 1)              AS median_cycle_days,
    MIN(cycle_days)                           AS min_cycle_days,
    MAX(cycle_days)                           AS max_cycle_days,
    ROUND(QUANTILE_CONT(cycle_days, 0.90), 1) AS p90_cycle_days
FROM recalls
WHERE cycle_days IS NOT NULL
  AND classification IS NOT NULL
  AND (? IS NULL OR recall_initiation_date >= CAST(? AS DATE))
  AND (? IS NULL OR recall_initiation_date <= CAST(? AS DATE))
GROUP BY classification
ORDER BY
    CASE classification
        WHEN 'Class I'   THEN 1
        WHEN 'Class II'  THEN 2
        WHEN 'Class III' THEN 3
        ELSE 4
    END;
