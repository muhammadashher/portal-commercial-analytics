-- Monthly commercial KPIs by vertical: revenue, active accounts, ARPA, logo churn, YoY growth
WITH base AS (
    SELECT vertical, month,
           COUNT(DISTINCT account_id)            AS active_accounts,
           SUM(revenue)                          AS revenue,
           SUM(is_new)                           AS new_accounts,
           SUM(churned)                          AS churned_accounts,
           SUM(CASE WHEN package_change = 'Upgrade' THEN 1 ELSE 0 END) AS upgrades
    FROM account_monthly
    GROUP BY vertical, month
)
SELECT vertical, month, active_accounts, new_accounts, churned_accounts, upgrades,
       ROUND(revenue, 0)                                     AS revenue,
       ROUND(revenue * 1.0 / active_accounts, 0)             AS arpa,
       ROUND(churned_accounts * 1.0 / active_accounts, 4)    AS logo_churn_rate,
       ROUND(revenue * 1.0 / LAG(revenue, 12) OVER w - 1, 4) AS yoy_growth
FROM base
WINDOW w AS (PARTITION BY vertical ORDER BY month)
ORDER BY vertical, month;
