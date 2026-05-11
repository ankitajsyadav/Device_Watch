-- Distribution of recalls by hazard classification.
-- Class I  = reasonable probability of serious adverse health consequences
-- Class II = temporary or medically reversible adverse health consequences
-- Class III = unlikely to cause adverse health consequences
SELECT
    classification,
    COUNT(*)                                            AS recall_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)  AS pct_of_total
FROM recalls
WHERE classification IS NOT NULL
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
