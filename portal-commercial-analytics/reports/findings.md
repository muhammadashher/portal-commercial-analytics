# Findings: Property & Jobs Commercial Performance (Oct 2024 - Sep 2026)

> Synthetic data built to mimic a UAE property and jobs classifieds portal. Competitor figures are illustrative.

## 1. Headline performance (Sep 2026)
- **Property** revenue AED 3,191,500/month, 29.2% YoY, 470 active agencies; 12-month NRR 83.0%, GRR 77.9%.
- **Jobs** revenue AED 789,161/month, 16.8% YoY, 418 active employers; 12-month NRR 78.0%, GRR 71.7%.
- Last-12-month contribution margin: Property 61.4%, Jobs 54.1%.

## 2. Target setting: equal split vs bottom-up capacity model
The legacy method takes last quarter's revenue x 1.12 and splits it equally across reps, ignoring the size and health of each rep's book. The bottom-up model projects each rep's book (trailing churn) plus new-business run-rate, then scales to the same company goal.

| Q3 2026 backtest | Legacy (equal split) | Bottom-up model |
|---|---|---|
| Attainment range | 43.1% - 147.4% | 86.2% - 104.1% |
| Attainment std dev | 0.303 | 0.048 |
| Reps within +/-10% of target | 38.9% | 72.2% |
| Target error (MAPE) | 33.4% | 8.9% |

Q4 2026 targets (goal +10% vs Q3): Property AED 10,175,000, Jobs AED 2,535,817 for the quarter; per-rep monthly targets in `outputs/q4_2026_rep_targets.csv` and `outputs/Q4_2026_Target_Model.xlsx`.

## 3. Sales productivity
- Top-quartile Property reps convert 11.6% of meetings to deals vs 5.2% for the bottom quartile; pairing and call-review sessions are the first lever.

## 4. Churn risk
- Logistic-regression churn model: AUC 0.65 on Apr-Sep 2026 (out of time); the riskiest 20% of accounts contain 39.4% of churn.
- Watchlist: 87 accounts worth AED 114,393/month (`outputs/churn_watchlist.csv`).
- Strongest risk drivers: weak_engagement, small_segment (raise risk); utilization, discount_pct (lower risk).

## 5. Discounts and upsell
- Property churn is 2.1%/month at 15%+ discounts vs 2.4% at 0-10%: deep discounts buy little extra retention, yet cost AED 3,833,149 in the last 12 months (of AED 5,605,186 total).
- 11 accounts have used 85%+ of their package for 3 straight months; upgrading them is worth AED 30,357/month.

## 6. Pricing vs competitors (illustrative)
- Entry tier, Competitor A: cost per lead AED 75.23 (+23% vs our portal)
- Entry tier, Competitor B: cost per lead AED 64.86 (+6% vs our portal)
- Mid tier, Competitor A: cost per lead AED 73.69 (+35% vs our portal)
- Mid tier, Competitor B: cost per lead AED 59.80 (+10% vs our portal)
- Top tier, Competitor A: cost per lead AED 66.15 (+52% vs our portal)
- Top tier, Competitor B: cost per lead AED 48.46 (+11% vs our portal)

## Recommendations
1. Replace equal-split targets with the bottom-up model from Q4 2026.
2. Give reps the weekly churn watchlist and run save calls on the top-risk accounts.
3. Cap standard discounts at 10%; deeper discounts need manager approval.
4. Launch an upgrade campaign for high-usage accounts, supported by a sales enablement kit.
5. Lead sales pitches with cost per lead, where the portal is competitive.