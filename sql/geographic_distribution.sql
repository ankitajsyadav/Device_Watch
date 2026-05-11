-- Recall count by state of the recalling firm. NULL/blank states roll up
-- as 'Unknown' so the total matches the underlying row count.
SELECT
    COALESCE(NULLIF(TRIM(state), ''), 'Unknown') AS state,
    COUNT(*)                                      AS recall_count,
    SUM(CASE WHEN classification = 'Class I' THEN 1 ELSE 0 END) AS class_i_count
FROM recalls
WHERE country = 'United States'
  AND (? IS NULL OR recall_initiation_date >= CAST(? AS DATE))
  AND (? IS NULL OR recall_initiation_date <= CAST(? AS DATE))
GROUP BY 1
ORDER BY recall_count DESC;
