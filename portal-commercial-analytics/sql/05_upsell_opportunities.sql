-- Accounts using >= 85% of their package for 3 consecutive months and not on the top package
WITH ranked AS (
    SELECT account_id, vertical, rep_id, package, month, utilization, revenue, discount_pct,
           ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY month DESC) AS rn
    FROM account_monthly
),
last3 AS (
    SELECT account_id, vertical, rep_id,
           MAX(CASE WHEN rn = 1 THEN package END) AS package,
           MAX(CASE WHEN rn = 1 THEN month END)   AS last_month,
           MIN(utilization)                       AS min_util_3m,
           AVG(revenue)                           AS avg_revenue_3m,
           MAX(discount_pct)                      AS discount_pct,
           COUNT(*)                               AS months,
           COUNT(DISTINCT package)                AS packages_held
    FROM ranked WHERE rn <= 3
    GROUP BY account_id, vertical, rep_id
)
SELECT * FROM last3
WHERE months = 3 AND packages_held = 1
  AND last_month = (SELECT MAX(month) FROM account_monthly)
  AND min_util_3m >= 0.85
  AND package NOT IN ('Premium', 'Unlimited')
ORDER BY avg_revenue_3m DESC;
