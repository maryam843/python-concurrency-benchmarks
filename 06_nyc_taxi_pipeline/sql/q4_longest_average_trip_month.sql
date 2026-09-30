-- Month with the longest average trip distance (miles); average duration shown alongside.
SELECT month,
       distance_sum / rows_clean AS avg_distance_mi,
       duration_min_sum / rows_clean AS avg_duration_min
FROM monthly
ORDER BY avg_distance_mi DESC, month
LIMIT 1;
