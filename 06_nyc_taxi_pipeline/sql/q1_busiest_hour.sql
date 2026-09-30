-- Busiest pickup hour of the day over the whole year (clean trips).
SELECT hour, SUM(trips) AS trips
FROM hourly
GROUP BY hour
ORDER BY trips DESC, hour
LIMIT 1;
