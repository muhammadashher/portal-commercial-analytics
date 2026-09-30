-- 12-month net revenue retention (NRR) and gross revenue retention (GRR) by vertical.
-- Base = accounts active 12 months before the measured month.
WITH m AS (
    SELECT account_id, vertical, month, revenue FROM account_monthly
),
pairs AS (
    SELECT cur.month, prev.vertical, prev.account_id,
           prev.revenue             AS base_revenue,
           COALESCE(nxt.revenue, 0) AS current_revenue
    FROM (SELECT DISTINCT month FROM m) cur
    JOIN m prev ON prev.month = STRFTIME('%Y-%m', DATE(cur.month || '-01', '-12 months'))
    LEFT JOIN m nxt ON nxt.account_id = prev.account_id AND nxt.month = cur.month
)
SELECT vertical, month,
       COUNT(*)                                                              AS base_accounts,
       ROUND(SUM(current_revenue) / SUM(base_revenue), 4)                    AS nrr,
       ROUND(SUM(MIN(current_revenue, base_revenue)) / SUM(base_revenue), 4) AS grr
FROM pairs
GROUP BY vertical, month
ORDER BY vertical, month;
