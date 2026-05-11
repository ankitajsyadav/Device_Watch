-- Top recalling firms in the selected date range, with severity mix and
-- average cycle time. Limit and class-I-share threshold for repeat-offender
-- detection are bound parameters.
SELECT
    recalling_firm,
    COUNT(*)                                                       AS total_recalls,
    SUM(CASE WHEN classification = 'Class I'  THEN 1 ELSE 0 END)   AS class_i_count,
    SUM(CASE WHEN classification = 'Class II' THEN 1 ELSE 0 END)   AS class_ii_count,
    SUM(CASE WHEN classification = 'Class III' THEN 1 ELSE 0 END)  AS class_iii_count,
    ROUND(AVG(cycle_days), 1)                                      AS avg_cycle_days,
    ROUND(
        100.0 * SUM(CASE WHEN classification = 'Class I' THEN 1 ELSE 0 END) / COUNT(*),
        1
    )                                                              AS pct_class_i
FROM recalls
WHERE recalling_firm IS NOT NULL
  AND (? IS NULL OR recall_initiation_date >= CAST(? AS DATE))
  AND (? IS NULL OR recall_initiation_date <= CAST(? AS DATE))
GROUP BY recalling_firm
HAVING COUNT(*) >= 2
ORDER BY total_recalls DESC
LIMIT ?;
