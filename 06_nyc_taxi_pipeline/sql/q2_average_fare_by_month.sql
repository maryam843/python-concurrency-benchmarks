-- Average fare (fare_amount, USD) per month over clean trips.
SELECT month, fare_sum / rows_clean AS avg_fare
FROM monthly
ORDER BY month;
