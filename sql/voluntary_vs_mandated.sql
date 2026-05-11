-- Voluntary (firm-initiated) vs FDA-mandated recalls. The vast majority
-- are voluntary; large swings in the mandated share are worth investigating.
SELECT
    COALESCE(voluntary_mandated, 'Unknown')               AS initiation_type,
    COUNT(*)                                               AS recall_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)     AS pct_of_total
FROM recalls
WHERE (? IS NULL OR recall_initiation_date >= CAST(? AS DATE))
  AND (? IS NULL OR recall_initiation_date <= CAST(? AS DATE))
GROUP BY 1
ORDER BY recall_count DESC;
