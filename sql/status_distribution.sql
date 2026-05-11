-- Recall status distribution (Ongoing, Completed, Terminated, Pending).
-- Useful for the Operations page -- shows backlog of recalls still in flight.
SELECT
    COALESCE(status, 'Unknown')                          AS status,
    COUNT(*)                                              AS recall_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)    AS pct_of_total
FROM recalls
WHERE (? IS NULL OR recall_initiation_date >= CAST(? AS DATE))
  AND (? IS NULL OR recall_initiation_date <= CAST(? AS DATE))
GROUP BY 1
ORDER BY recall_count DESC;
