-- Share of trips removed by the cleaning rules, per month.
SELECT month, rows_raw, rows_clean,
       CAST(rows_raw - rows_clean AS REAL) / rows_raw AS share_removed
FROM monthly
ORDER BY month;
