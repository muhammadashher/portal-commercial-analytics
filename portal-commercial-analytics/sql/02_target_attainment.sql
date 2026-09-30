-- Rep revenue vs legacy target, attainment and monthly rank within vertical
SELECT rep_id, vertical, month, quarter,
       ROUND(book_revenue, 0)                            AS revenue,
       revenue_target,
       ROUND(book_revenue * 1.0 / revenue_target, 3)     AS attainment,
       RANK() OVER (PARTITION BY vertical, month
                    ORDER BY book_revenue * 1.0 / revenue_target DESC) AS attainment_rank,
       ROUND(AVG(book_revenue * 1.0 / revenue_target) OVER (
             PARTITION BY rep_id ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 3) AS attainment_3m_avg
FROM rep_monthly
ORDER BY vertical, rep_id, month;
