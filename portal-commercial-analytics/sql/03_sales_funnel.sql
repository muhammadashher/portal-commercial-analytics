-- Inside-sales productivity (last 6 months): calls -> meetings -> deals funnel and revenue per rep
WITH recent AS (
    SELECT * FROM rep_monthly
    WHERE month > STRFTIME('%Y-%m', DATE((SELECT MAX(month) FROM rep_monthly) || '-01', '-6 months'))
)
SELECT rep_id, vertical,
       SUM(calls)                                                AS calls,
       SUM(meetings)                                             AS meetings,
       SUM(new_deals)                                            AS new_deals,
       SUM(upgrades)                                             AS upgrades,
       ROUND(SUM(meetings) * 1.0 / SUM(calls), 4)                AS call_to_meeting,
       ROUND(SUM(new_deals) * 1.0 / NULLIF(SUM(meetings), 0), 4) AS meeting_to_deal,
       ROUND(SUM(new_revenue), 0)                                AS new_business_revenue,
       ROUND(AVG(book_revenue), 0)                               AS avg_monthly_book_revenue,
       NTILE(4) OVER (PARTITION BY vertical
                      ORDER BY SUM(new_deals) * 1.0 / SUM(calls) DESC) AS productivity_quartile
FROM recent
GROUP BY rep_id, vertical
ORDER BY vertical, productivity_quartile, rep_id;
