-- Top 10 pickup zones for the year (clean trips), with names from the TLC zone lookup.
SELECT t.zone_id, z.borough, z.zone, SUM(t.trips) AS trips
FROM zone_trips AS t
LEFT JOIN zones AS z ON z.zone_id = t.zone_id
GROUP BY t.zone_id
ORDER BY trips DESC, t.zone_id
LIMIT 10;
