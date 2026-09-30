"""Commercial analysis for the Property & Jobs verticals.

1. KPI, retention, funnel, upsell and discount analysis (SQL in /sql)
2. Account churn-risk model (logistic regression, time-based validation)
3. Target-setting: legacy top-down vs bottom-up capacity model (backtest on Q3 2026)
4. Q4 2026 rep targets using the bottom-up model
5. Monthly P&L / contribution margin by vertical
6. Pricing benchmark: cost per lead vs competitors (illustrative data)
"""
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

SQL_FILES = {
    "monthly_kpis": "01_monthly_kpis.sql",
    "target_attainment": "02_target_attainment.sql",
    "sales_funnel": "03_sales_funnel.sql",
    "revenue_retention": "04_net_revenue_retention.sql",
    "upsell_opportunities": "05_upsell_opportunities.sql",
    "discount_effectiveness": "06_discount_effectiveness.sql",
}


def run_sql(con):
    return {name: pd.read_sql((C.SQL_DIR / f).read_text(), con) for name, f in SQL_FILES.items()}


# ---------------------------------------------------------------- churn model
def churn_features(am):
    df = am.sort_values(["account_id", "month"]).copy()
    df["eng_per_unit"] = df["engagement"] / df["units_used"]
    df["eng_ratio"] = df["eng_per_unit"] / df.groupby(["vertical", "month"])["eng_per_unit"].transform("median")
    g = df.groupby("account_id")
    df["eng_ratio_3m"] = g["eng_ratio"].transform(lambda s: s.rolling(3, min_periods=1).mean())
    df["util_change"] = g["utilization"].diff().fillna(0)
    df["tenure"] = df["tenure_months"].clip(upper=36)
    df["is_new_account"] = (df["tenure_months"] < 3).astype(int)
    df["is_jobs"] = (df["vertical"] == "Jobs").astype(int)
    df["low_tier_package"] = df["package"].isin(["Basic", "Pay-per-Post"]).astype(int)
    df["weak_engagement"] = (df["eng_ratio"] < 0.80).astype(int)
    df["low_utilization"] = (df["utilization"] < 0.40).astype(int)
    df["small_segment"] = df["segment"].isin(["Small", "SME"]).astype(int)
    return df


FEATURES = ["utilization", "eng_ratio", "eng_ratio_3m", "util_change", "discount_pct",
            "tenure", "is_new_account", "is_jobs", "low_tier_package",
            "weak_engagement", "low_utilization", "small_segment"]


def churn_model(am, accounts):
    df = churn_features(am.merge(accounts[["account_id", "segment"]], on="account_id"))
    train = df[df["month"] <= "2026-03"]
    test = df[df["month"] > "2026-03"]
    model = make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000))
    model.fit(train[FEATURES], train["churned"])
    test = test.assign(risk=model.predict_proba(test[FEATURES])[:, 1])
    auc = roc_auc_score(test["churned"], test["risk"])
    cut = test["risk"].quantile(0.80)
    capture = test.loc[test["risk"] >= cut, "churned"].sum() / test["churned"].sum()

    latest = df[df["month"] == df["month"].max()].copy()
    latest["risk"] = model.predict_proba(latest[FEATURES])[:, 1]
    latest = latest[latest["churned"] == 0]
    high = latest[latest["risk"] >= latest["risk"].quantile(0.90)]
    coefs = pd.Series(model[-1].coef_[0], index=FEATURES).sort_values()
    watchlist = high[["account_id", "vertical", "rep_id", "package", "revenue", "utilization",
                      "eng_ratio", "risk"]].sort_values("risk", ascending=False)
    return {"auc": auc, "top20_capture": capture, "at_risk_accounts": len(high),
            "at_risk_monthly_revenue": high["revenue"].sum(), "coefficients": coefs,
            "watchlist": watchlist}


# ---------------------------------------------------------------- target setting
def bottom_up_expectation(rm, am, as_of, months_ahead=3):
    """Expected monthly revenue per rep for the next quarter, using data up to `as_of`.

    expected_k = book * (1 - churn)^k + new_rate * sum_{j=1..k} (1 - churn)^(k - j)
    where churn = trailing-6-month revenue-weighted churn of the rep's book and
    new_rate = trailing-6-month average first-month revenue from new accounts.
    """
    hist_months = sorted(m for m in rm["month"].unique() if m <= as_of)[-6:]
    h = rm[rm["month"].isin(hist_months)]
    churn_rev = (am[am["month"].isin(hist_months) & (am["churned"] == 1)]
                 .groupby("rep_id")["revenue"].sum())
    book_rev = h.groupby("rep_id")["book_revenue"].sum()
    churn_rate = (churn_rev.reindex(book_rev.index).fillna(0) / book_rev).clip(0, 0.2)
    new_rate = h.groupby("rep_id")["new_revenue"].mean()
    base = rm[rm["month"] == as_of].set_index("rep_id")["book_revenue"]
    out = pd.DataFrame({"base_book": base, "trailing_churn": churn_rate, "new_rate": new_rate})
    for k in range(1, months_ahead + 1):
        retained = out["base_book"] * (1 - out["trailing_churn"]) ** k
        new = sum(out["new_rate"] * (1 - out["trailing_churn"]) ** (k - j) for j in range(1, k + 1))
        out[f"exp_m{k}"] = retained + new
    out["expected_q"] = out[[f"exp_m{k}" for k in range(1, months_ahead + 1)]].sum(axis=1)
    return out.join(rm.drop_duplicates("rep_id").set_index("rep_id")["vertical"])


def allocate(expect, vertical_goal):
    """Scale each rep's expected revenue so the vertical total equals the company goal."""
    e = expect.copy()
    e["share"] = e["expected_q"] / e.groupby("vertical")["expected_q"].transform("sum")
    e["target_q"] = e["share"] * e["vertical"].map(vertical_goal)
    for k in (1, 2, 3):
        e[f"target_m{k}"] = e["target_q"] * e[f"exp_m{k}"] / e["expected_q"]
    return e


def target_backtest(rm, am):
    q_months = ["2026-07", "2026-08", "2026-09"]
    q = rm[rm["month"].isin(q_months)]
    actual = q.groupby("rep_id")["book_revenue"].sum()
    legacy = q.groupby("rep_id")["revenue_target"].sum()
    vertical = q.drop_duplicates("rep_id").set_index("rep_id")["vertical"]
    goal = legacy.groupby(vertical).sum()             # same company ambition for both methods
    bu = allocate(bottom_up_expectation(rm, am, "2026-06"), goal)["target_q"]

    def stats(target):
        att = actual / target
        return {"attainment_min": att.min(), "attainment_max": att.max(),
                "attainment_std": att.std(), "within_10pct": (att.between(0.9, 1.1)).mean(),
                "mape": (abs(target - actual) / actual).mean()}
    table = pd.DataFrame({"vertical": vertical, "actual_q3": actual, "legacy_target_q3": legacy,
                          "bottom_up_target_q3": bu})
    table["legacy_attainment"] = table["actual_q3"] / table["legacy_target_q3"]
    table["bottom_up_attainment"] = table["actual_q3"] / table["bottom_up_target_q3"]
    return {"legacy": stats(legacy), "bottom_up": stats(bu), "table": table.round(3)}


def q4_targets(rm, am):
    q3 = rm[rm["month"].isin(["2026-07", "2026-08", "2026-09"])]
    goal = q3.groupby("vertical")["book_revenue"].sum() * (1 + C.Q4_2026_GROWTH_GOAL)
    t = allocate(bottom_up_expectation(rm, am, "2026-09"), goal)
    t = t.rename(columns={"target_m1": "target_oct", "target_m2": "target_nov", "target_m3": "target_dec"})
    return t.reset_index().rename(columns={"index": "rep_id"}), goal


# ---------------------------------------------------------------- P&L
def pnl(am, rm, costs):
    rev = am.groupby(["vertical", "month"]).agg(revenue=("revenue", "sum"),
                                                list_revenue=("list_revenue", "sum")).reset_index()
    new = rm.groupby(["vertical", "month"]).agg(new_revenue=("new_revenue", "sum"),
                                                reps=("rep_id", "nunique")).reset_index()
    p = rev.merge(new, on=["vertical", "month"]).merge(costs, on=["vertical", "month"])
    p["discounts"] = (am.assign(d=am["list_revenue"] * am["discount_pct"])
                      .groupby(["vertical", "month"])["d"].sum().values)
    p["payment_fees"] = p["revenue"] * C.PAYMENT_FEE_RATE
    p["tech_allocation"] = p["revenue"] * C.TECH_ALLOCATION_RATE
    p["sales_team_cost"] = p["reps"] * C.REP_MONTHLY_COST
    # commission = rate x first 3 months of revenue from new accounts, booked in the win month
    p["commissions"] = p["new_revenue"] * 3 * C.COMMISSION_RATE
    p["contribution"] = p["revenue"] - p[["payment_fees", "tech_allocation", "sales_team_cost",
                                          "commissions", "marketing_spend"]].sum(axis=1)
    p["contribution_margin"] = p["contribution"] / p["revenue"]
    return p.round(2)


# ---------------------------------------------------------------- pricing
def pricing_benchmark(am, comp):
    prop = am[am["vertical"] == "Property"]
    recent = prop[prop["month"] >= "2026-07"]
    lpl = (recent["engagement"].sum() / recent["units_used"].sum())
    util = recent["utilization"].mean()
    c = comp[comp["quarter"] == "2026Q3"].copy()
    c["leads_per_month"] = c["listing_credits"] * util * lpl * c["lead_index"]
    c["cost_per_lead_aed"] = c["monthly_price_aed"] / c["leads_per_month"]
    ours = c[c["portal"] == "Our Portal"].set_index("tier")["cost_per_lead_aed"]
    c["vs_our_portal"] = c["cost_per_lead_aed"] / c["tier"].map(ours) - 1
    return c.round(3), lpl


# ---------------------------------------------------------------- main
def main():
    C.OUT_DIR.mkdir(exist_ok=True)
    C.REPORT_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(C.DB_PATH)
    am = pd.read_sql("SELECT * FROM account_monthly", con)
    rm = pd.read_sql("SELECT * FROM rep_monthly", con)
    costs = pd.read_sql("SELECT * FROM marketing_costs", con)
    comp = pd.read_sql("SELECT * FROM competitor_pricing", con)

    res = run_sql(con)
    for name, df in res.items():
        df.to_csv(C.OUT_DIR / f"{name}.csv", index=False)

    accounts = pd.read_sql("SELECT account_id, segment FROM accounts", con)
    cm = churn_model(am, accounts)
    cm["watchlist"].to_csv(C.OUT_DIR / "churn_watchlist.csv", index=False)
    bt = target_backtest(rm, am)
    bt["table"].to_csv(C.OUT_DIR / "target_backtest_q3_2026.csv")
    q4, goal = q4_targets(rm, am)
    q4.round(0).to_csv(C.OUT_DIR / "q4_2026_rep_targets.csv", index=False)
    p = pnl(am, rm, costs)
    p.to_csv(C.OUT_DIR / "pnl_by_vertical.csv", index=False)
    price, lpl = pricing_benchmark(am, comp)
    price.to_csv(C.OUT_DIR / "pricing_benchmark.csv", index=False)

    # ---- upsell sizing
    ups = res["upsell_opportunities"].copy()
    next_price = {"Basic": 7500, "Standard": 15000, "Pay-per-Post": 1999, "Pack-5": 4999}
    ups["uplift_monthly"] = (ups["package"].map(next_price) * (1 - ups["discount_pct"])
                             - ups["avg_revenue_3m"]).clip(lower=0)
    ups = ups[ups["uplift_monthly"] > 0]
    ups.to_csv(C.OUT_DIR / "upsell_opportunities_sized.csv", index=False)

    # ---- headline metrics
    k = res["monthly_kpis"]
    last = k[k["month"] == k["month"].max()].set_index("vertical")
    ret = res["revenue_retention"].groupby("vertical").last()
    fun = res["sales_funnel"]
    top = fun[fun.productivity_quartile == 1].groupby("vertical")["meeting_to_deal"].mean()
    bot = fun[fun.productivity_quartile == 4].groupby("vertical")["meeting_to_deal"].mean()
    d = res["discount_effectiveness"]
    dp = d[d.vertical == "Property"]
    low_d = np.average(dp[dp.discount_pct <= 0.10]["monthly_churn_rate"], weights=dp[dp.discount_pct <= 0.10]["accounts"])
    high_d = np.average(dp[dp.discount_pct >= 0.15]["monthly_churn_rate"], weights=dp[dp.discount_pct >= 0.15]["accounts"])
    last12 = am[am["month"] > "2025-09"]
    disc_12m = (last12["list_revenue"] * last12["discount_pct"]).sum()
    disc_12m_deep = (last12.loc[last12.discount_pct >= 0.15, "list_revenue"]
                     * last12.loc[last12.discount_pct >= 0.15, "discount_pct"]).sum()
    p12 = p[p["month"] > "2025-09"].groupby("vertical")[["revenue", "contribution"]].sum()
    p12["margin"] = p12["contribution"] / p12["revenue"]

    metrics = {
        "rows_account_monthly": len(am),
        "accounts_total": int(am["account_id"].nunique()),
        "revenue_sep_2026": last["revenue"].to_dict(),
        "yoy_growth_sep_2026": last["yoy_growth"].to_dict(),
        "active_accounts_sep_2026": last["active_accounts"].to_dict(),
        "nrr_12m": ret["nrr"].to_dict(), "grr_12m": ret["grr"].to_dict(),
        "churn_model_auc": cm["auc"], "churn_top20_capture": cm["top20_capture"],
        "at_risk_accounts": cm["at_risk_accounts"], "at_risk_monthly_revenue": cm["at_risk_monthly_revenue"],
        "target_backtest": {"legacy": bt["legacy"], "bottom_up": bt["bottom_up"]},
        "q4_goal": goal.to_dict(),
        "meeting_to_deal_top_quartile": top.to_dict(), "meeting_to_deal_bottom_quartile": bot.to_dict(),
        "property_churn_discount_le10": low_d, "property_churn_discount_ge15": high_d,
        "discount_given_12m": disc_12m, "discount_given_12m_deep": disc_12m_deep,
        "upsell_accounts": len(ups), "upsell_uplift_monthly": ups["uplift_monthly"].sum(),
        "contribution_margin_12m": p12["margin"].to_dict(),
        "revenue_12m": p12["revenue"].to_dict(),
        "leads_per_listing_q3": lpl,
        "pricing": price[["portal", "tier", "cost_per_lead_aed", "vs_our_portal"]].to_dict("records"),
    }
    (C.OUT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    write_report(metrics, cm, bt, q4)
    print(json.dumps({k: metrics[k] for k in ["churn_model_auc", "churn_top20_capture",
                                              "target_backtest", "upsell_accounts",
                                              "upsell_uplift_monthly", "contribution_margin_12m"]},
                     indent=2, default=float))
    return metrics


def aed(x):
    return f"AED {x:,.0f}"


def pct(x):
    return f"{x * 100:.1f}%"


def write_report(m, cm, bt, q4):
    L, B = bt["legacy"], bt["bottom_up"]
    drivers = cm["coefficients"]
    lines = [
        "# Findings: Property & Jobs Commercial Performance (Oct 2024 - Sep 2026)",
        "",
        "> Synthetic data built to mimic a UAE property and jobs classifieds portal. "
        "Competitor figures are illustrative.",
        "",
        "## 1. Headline performance (Sep 2026)",
        f"- **Property** revenue {aed(m['revenue_sep_2026']['Property'])}/month, "
        f"{pct(m['yoy_growth_sep_2026']['Property'])} YoY, {m['active_accounts_sep_2026']['Property']} active agencies; "
        f"12-month NRR {pct(m['nrr_12m']['Property'])}, GRR {pct(m['grr_12m']['Property'])}.",
        f"- **Jobs** revenue {aed(m['revenue_sep_2026']['Jobs'])}/month, "
        f"{pct(m['yoy_growth_sep_2026']['Jobs'])} YoY, {m['active_accounts_sep_2026']['Jobs']} active employers; "
        f"12-month NRR {pct(m['nrr_12m']['Jobs'])}, GRR {pct(m['grr_12m']['Jobs'])}.",
        f"- Last-12-month contribution margin: Property {pct(m['contribution_margin_12m']['Property'])}, "
        f"Jobs {pct(m['contribution_margin_12m']['Jobs'])}.",
        "",
        "## 2. Target setting: equal split vs bottom-up capacity model",
        "The legacy method takes last quarter's revenue x 1.12 and splits it equally across reps, "
        "ignoring the size and health of each rep's book. The bottom-up model projects each rep's "
        "book (trailing churn) plus new-business run-rate, then scales to the same company goal.",
        "",
        "| Q3 2026 backtest | Legacy (equal split) | Bottom-up model |",
        "|---|---|---|",
        f"| Attainment range | {pct(L['attainment_min'])} - {pct(L['attainment_max'])} | "
        f"{pct(B['attainment_min'])} - {pct(B['attainment_max'])} |",
        f"| Attainment std dev | {L['attainment_std']:.3f} | {B['attainment_std']:.3f} |",
        f"| Reps within +/-10% of target | {pct(L['within_10pct'])} | {pct(B['within_10pct'])} |",
        f"| Target error (MAPE) | {pct(L['mape'])} | {pct(B['mape'])} |",
        "",
        f"Q4 2026 targets (goal +{C.Q4_2026_GROWTH_GOAL:.0%} vs Q3): Property {aed(m['q4_goal']['Property'])}, "
        f"Jobs {aed(m['q4_goal']['Jobs'])} for the quarter; per-rep monthly targets in "
        "`outputs/q4_2026_rep_targets.csv` and `outputs/Q4_2026_Target_Model.xlsx`.",
        "",
        "## 3. Sales productivity",
        f"- Top-quartile Property reps convert {pct(m['meeting_to_deal_top_quartile']['Property'])} of meetings "
        f"to deals vs {pct(m['meeting_to_deal_bottom_quartile']['Property'])} for the bottom quartile; "
        "pairing and call-review sessions are the first lever.",
        "",
        "## 4. Churn risk",
        f"- Logistic-regression churn model: AUC {m['churn_model_auc']:.2f} on Apr-Sep 2026 (out of time); "
        f"the riskiest 20% of accounts contain {pct(m['churn_top20_capture'])} of churn.",
        f"- Watchlist: {m['at_risk_accounts']} accounts worth {aed(m['at_risk_monthly_revenue'])}/month "
        "(`outputs/churn_watchlist.csv`).",
        f"- Strongest risk drivers: {', '.join(drivers.index[-2:][::-1])} (raise risk); "
        f"{', '.join(drivers.index[:2])} (lower risk).",
        "",
        "## 5. Discounts and upsell",
        f"- Property churn is {pct(m['property_churn_discount_ge15'])}/month at 15%+ discounts vs "
        f"{pct(m['property_churn_discount_le10'])} at 0-10%: deep discounts buy little extra retention, yet cost "
        f"{aed(m['discount_given_12m_deep'])} in the last 12 months (of {aed(m['discount_given_12m'])} total).",
        f"- {m['upsell_accounts']} accounts have used 85%+ of their package for 3 straight months; "
        f"upgrading them is worth {aed(m['upsell_uplift_monthly'])}/month.",
        "",
        "## 6. Pricing vs competitors (illustrative)",
    ]
    for r in m["pricing"]:
        if r["portal"] != "Our Portal":
            lines.append(f"- {r['tier']} tier, {r['portal']}: cost per lead AED {r['cost_per_lead_aed']:.2f} "
                         f"({'+' if r['vs_our_portal'] >= 0 else ''}{r['vs_our_portal'] * 100:.0f}% vs our portal)")
    lines += ["", "## Recommendations",
              "1. Replace equal-split targets with the bottom-up model from Q4 2026.",
              "2. Give reps the weekly churn watchlist and run save calls on the top-risk accounts.",
              "3. Cap standard discounts at 10%; deeper discounts need manager approval.",
              "4. Launch an upgrade campaign for high-usage accounts, supported by a sales enablement kit.",
              "5. Lead sales pitches with cost per lead, where the portal is competitive."]
    (C.REPORT_DIR / "findings.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
