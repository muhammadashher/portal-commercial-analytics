-- Does discounting buy retention? Churn rate and revenue given away by discount band
SELECT vertical,
       CAST(ROUND(discount_pct * 100) AS INTEGER) || '%'    AS discount_band,
       discount_pct,
       COUNT(DISTINCT account_id)                           AS accounts,
       ROUND(AVG(churned), 4)                               AS monthly_churn_rate,
       ROUND(SUM(list_revenue * discount_pct), 0)           AS discount_given_aed
FROM account_monthly
GROUP BY vertical, discount_pct
ORDER BY vertical, discount_pct;
