"""Generate a realistic synthetic dataset for a UAE property & jobs classifieds portal.

Simulates 24 months of inside-sales activity: reps make calls and meetings, win new
agencies / employers, accounts buy packages, use listing credits or job slots, receive
leads / applications, upgrade, downgrade and churn. Legacy sales targets are set the
"top-down" way (last quarter x growth, split equally across reps).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

rng = np.random.default_rng(C.SEED)
MONTHS = pd.period_range(C.START_MONTH, periods=C.N_MONTHS, freq="M")

PROP_ORDER = list(C.PROPERTY_PACKAGES)
JOBS_ORDER = list(C.JOBS_PACKAGES)


# ------------------------------------------------------------------ reps
def make_reps():
    rows = []
    for vertical, n, prefix in [("Property", C.PROPERTY_REPS, "PR"), ("Jobs", C.JOBS_REPS, "JR")]:
        for i in range(1, n + 1):
            rows.append({
                "rep_id": f"{prefix}{i:02d}",
                "vertical": vertical,
                "skill": float(np.clip(rng.normal(1.0, 0.22), 0.6, 1.5)),
                "effort": float(np.clip(rng.normal(1.0, 0.15), 0.7, 1.3)),
                "discount_propensity": float(rng.uniform(0.1, 0.9)),
            })
    return pd.DataFrame(rows)


def pick_discount(propensity):
    bands = np.array([0.0, 0.05, 0.10, 0.15, 0.20, 0.25])
    w = np.array([1.0, 1.0, 0.9, 0.7, 0.5, 0.35])
    w = w * np.linspace(1 - propensity, 1 + 2 * propensity, len(bands))
    return float(rng.choice(bands, p=w / w.sum()))


# ------------------------------------------------------------------ accounts
def new_property_account(acc_id, rep, start):
    tier = rng.choice(["Small", "Mid", "Large"], p=[0.6, 0.3, 0.1])
    pkg_p = {"Small": [0.7, 0.3, 0.0], "Mid": [0.2, 0.6, 0.2], "Large": [0.0, 0.3, 0.7]}[tier]
    return {
        "account_id": acc_id, "vertical": "Property", "rep_id": rep["rep_id"],
        "segment": tier, "area_or_sector": rng.choice(list(C.DUBAI_AREAS)),
        "package": rng.choice(PROP_ORDER, p=pkg_p),
        "discount_pct": pick_discount(rep["discount_propensity"]),
        "start_month": str(start), "util": {"Small": 0.55, "Mid": 0.68, "Large": 0.80}[tier]
        + rng.normal(0, 0.15),
    }


def new_jobs_account(acc_id, rep, start):
    size = rng.choice(["SME", "Mid-Market", "Enterprise"], p=[0.65, 0.27, 0.08])
    pkg_p = {"SME": [0.7, 0.28, 0.02], "Mid-Market": [0.3, 0.55, 0.15],
             "Enterprise": [0.05, 0.35, 0.6]}[size]
    return {
        "account_id": acc_id, "vertical": "Jobs", "rep_id": rep["rep_id"],
        "segment": size, "area_or_sector": rng.choice(list(C.JOB_SECTORS)),
        "package": rng.choice(JOBS_ORDER, p=pkg_p),
        "discount_pct": pick_discount(rep["discount_propensity"]) * 0.6,
        "start_month": str(start), "util": {"SME": 0.52, "Mid-Market": 0.65, "Enterprise": 0.78}[size]
        + rng.normal(0, 0.15),
    }


# ------------------------------------------------------------------ simulation
def simulate():
    reps = make_reps()
    rep_by_id = reps.set_index("rep_id").to_dict("index")
    for k in rep_by_id:
        rep_by_id[k]["rep_id"] = k

    accounts, active = {}, {}
    counter = {"Property": 0, "Jobs": 0}

    def add_account(vertical, rep_id, start, tenure=0):
        counter[vertical] += 1
        prefix = "AG" if vertical == "Property" else "EM"
        acc_id = f"{prefix}{counter[vertical]:05d}"
        maker = new_property_account if vertical == "Property" else new_jobs_account
        acc = maker(acc_id, rep_by_id[rep_id], start)
        acc["tenure"] = tenure
        acc["util"] = float(np.clip(acc["util"], 0.1, 0.98))
        acc["base_util"] = acc["util"]
        acc["low_util_streak"] = 0
        acc["high_util_streak"] = 0
        accounts[acc_id] = acc
        active[acc_id] = acc
        return acc

    # Opening book: uneven allocation across reps (some reps inherit bigger books)
    for vertical, n, n_reps in [("Property", C.PROPERTY_START_ACCOUNTS, C.PROPERTY_REPS),
                                ("Jobs", C.JOBS_START_ACCOUNTS, C.JOBS_REPS)]:
        rep_ids = reps.loc[reps.vertical == vertical, "rep_id"].to_numpy()
        weights = rng.dirichlet(np.full(n_reps, 3.0))
        for _ in range(n):
            add_account(vertical, rng.choice(rep_ids, p=weights), MONTHS[0] - 1,
                        tenure=int(rng.integers(3, 36)))

    monthly_rows, rep_rows = [], []
    for t, month in enumerate(MONTHS):
        m = month.month
        trend = 1 + 0.010 * t
        new_this_month = {r: [] for r in rep_by_id}

        # --- rep activity and new business
        for rep_id, rep in rep_by_id.items():
            prop = rep["vertical"] == "Property"
            season = (C.PROPERTY_SEASONALITY if prop else C.JOBS_SEASONALITY)[m]
            calls = int(rng.poisson((300 if prop else 340) * rep["effort"]))
            meetings = int(rng.binomial(calls, (0.050 if prop else 0.060) * min(rep["skill"], 1.3)))
            close = (0.085 if prop else 0.11) * rep["skill"] * season
            deals = int(rng.binomial(meetings, min(close, 0.4)))
            for _ in range(deals):
                acc = add_account(rep["vertical"], rep_id, month)
                new_this_month[rep_id].append(acc["account_id"])
            rep_rows.append({"rep_id": rep_id, "month": str(month), "calls": calls,
                             "meetings": meetings, "new_deals": deals})

        # --- account behaviour
        churned = []
        for acc_id, acc in list(active.items()):
            prop = acc["vertical"] == "Property"
            rep = rep_by_id[acc["rep_id"]]
            acc["util"] = float(np.clip(0.75 * acc["util"] + 0.25 * acc["base_util"]
                                        + rng.normal(0, 0.07), 0.05, 1.0))
            util = acc["util"]
            pkg = acc["package"]
            if prop:
                spec = C.PROPERTY_PACKAGES[pkg]
                units = max(1, int(round(spec["credits"] * util)))
                lpl = 3.2 * C.DUBAI_AREAS[acc["area_or_sector"]] * C.PROPERTY_SEASONALITY[m] * trend
                engagement = int(rng.poisson(units * lpl * rng.lognormal(0, 0.25)))
                addons = int(rng.poisson({"Small": 1.5, "Mid": 4, "Large": 10}[acc["segment"]] * util))
                list_price = spec["price"]
                revenue = list_price * (1 - acc["discount_pct"]) + addons * C.FEATURED_ADDON_PRICE
                eng_per_unit = engagement / units
                bench = 3.2 * C.PROPERTY_SEASONALITY[m] * trend
                base_churn = {"Small": 0.022, "Mid": 0.012, "Large": 0.006}[acc["segment"]]
            else:
                spec = C.JOBS_PACKAGES[pkg]
                if spec["slots"] is None:
                    units = max(1, int(rng.poisson(1.6 * util / 0.55)))
                    list_price = spec["price"] * units
                else:
                    units = max(1, int(round(spec["slots"] * util)))
                    list_price = spec["price"]
                apps = 22 * C.JOB_SECTORS[acc["area_or_sector"]] * C.JOBS_SEASONALITY[m] * trend
                engagement = int(rng.poisson(units * apps * rng.lognormal(0, 0.3)))
                addons = 0
                revenue = list_price * (1 - acc["discount_pct"])
                eng_per_unit = engagement / units
                bench = 22 * C.JOBS_SEASONALITY[m] * trend
                base_churn = {"Pay-per-Post": 0.034, "Pack-5": 0.019, "Unlimited": 0.009}[pkg]

            # churn drivers: weak lead/application performance, low usage, new accounts
            p = base_churn
            if eng_per_unit < 0.75 * bench:
                p *= 1.9
            if util < 0.40:
                p *= 1.7
            if acc["tenure"] < 3:
                p *= 1.3
            p *= 1 - 0.4 * acc["discount_pct"]          # discounts barely help retention
            p /= rep["skill"] ** 0.5
            churn_flag = int(rng.random() < min(p, 0.6))

            acc["high_util_streak"] = acc["high_util_streak"] + 1 if util >= 0.85 else 0
            acc["low_util_streak"] = acc["low_util_streak"] + 1 if util < 0.35 else 0
            order = PROP_ORDER if prop else JOBS_ORDER
            idx = order.index(pkg)
            change = "None"
            if not churn_flag:
                if acc["high_util_streak"] >= 2 and idx < 2 and rng.random() < 0.18 * rep["skill"]:
                    acc["package"] = order[idx + 1]; change = "Upgrade"
                    acc["util"] *= 0.6; acc["base_util"] *= 0.75
                elif acc["low_util_streak"] >= 2 and idx > 0 and rng.random() < 0.06:
                    acc["package"] = order[idx - 1]; change = "Downgrade"
                    acc["util"] = min(1.0, acc["util"] * 1.5); acc["base_util"] = min(0.95, acc["base_util"] * 1.3)

            monthly_rows.append({
                "account_id": acc_id, "month": str(month), "vertical": acc["vertical"],
                "rep_id": acc["rep_id"], "package": pkg, "list_revenue": round(list_price, 2),
                "discount_pct": acc["discount_pct"], "addon_units": addons,
                "revenue": round(revenue, 2), "units_used": units,
                "utilization": round(util, 3), "engagement": engagement,
                "is_new": int(acc["start_month"] == str(month)),
                "tenure_months": acc["tenure"], "package_change": change,
                "churned": churn_flag,
            })
            acc["tenure"] += 1
            if churn_flag:
                churned.append(acc_id)
        for acc_id in churned:
            accounts[acc_id]["end_month"] = str(month)
            active.pop(acc_id)

    acc_df = pd.DataFrame(accounts.values()).drop(
        columns=["util", "base_util", "tenure", "low_util_streak", "high_util_streak"])
    acc_df["end_month"] = acc_df.get("end_month")
    # initial package at acquisition is not tracked separately; package here = latest
    last_pkg = pd.DataFrame(monthly_rows).groupby("account_id")["package"].last()
    acc_df["current_package"] = acc_df["account_id"].map(last_pkg)
    acc_df = acc_df.drop(columns=["package"])
    return reps, acc_df, pd.DataFrame(monthly_rows), pd.DataFrame(rep_rows)


def add_rep_revenue_and_targets(rep_monthly, account_monthly, reps):
    """Rep book revenue, new/upsell revenue and legacy top-down targets."""
    am = account_monthly.copy()
    am["new_revenue"] = am["revenue"].where(am["is_new"] == 1, 0.0)
    book = am.groupby(["rep_id", "month"]).agg(
        book_revenue=("revenue", "sum"), new_revenue=("new_revenue", "sum"),
        active_accounts=("account_id", "nunique")).reset_index()
    upg = (am[am.package_change == "Upgrade"].groupby(["rep_id", "month"]).size()
           .rename("upgrades").reset_index())
    rm = rep_monthly.merge(book, on=["rep_id", "month"], how="left").merge(
        upg, on=["rep_id", "month"], how="left")
    rm["upgrades"] = rm["upgrades"].fillna(0).astype(int)
    rm = rm.merge(reps[["rep_id", "vertical"]], on="rep_id")

    # Legacy targets: previous quarter's vertical revenue x (1 + growth), split equally.
    rm["period"] = pd.PeriodIndex(rm["month"], freq="M")
    rm["quarter"] = rm["period"].dt.quarter.astype(str).radd(rm["period"].dt.year.astype(str) + "Q")
    vert_q = rm.groupby(["vertical", "quarter"])["book_revenue"].sum().reset_index()
    vert_q = vert_q.sort_values(["vertical", "quarter"])
    vert_q["prev_q_rev"] = vert_q.groupby("vertical")["book_revenue"].shift(1)
    first = vert_q["prev_q_rev"].isna()
    vert_q.loc[first, "prev_q_rev"] = vert_q.loc[first, "book_revenue"] / (1 + C.LEGACY_TARGET_GROWTH)
    n_reps = reps.groupby("vertical").size()
    vert_q["monthly_target_per_rep"] = (vert_q["prev_q_rev"] * (1 + C.LEGACY_TARGET_GROWTH)
                                        / 3 / vert_q["vertical"].map(n_reps))
    rm = rm.merge(vert_q[["vertical", "quarter", "monthly_target_per_rep"]], on=["vertical", "quarter"])
    rm = rm.rename(columns={"monthly_target_per_rep": "revenue_target"})
    rm["revenue_target"] = rm["revenue_target"].round(0)
    return rm.drop(columns=["period"]).sort_values(["rep_id", "month"])


def make_competitor_pricing():
    """Illustrative competitor benchmark (NOT real competitor prices)."""
    rows = []
    for q in ["2025Q4", "2026Q1", "2026Q2", "2026Q3"]:
        drift = {"2025Q4": 1.0, "2026Q1": 1.0, "2026Q2": 1.03, "2026Q3": 1.05}[q]
        for tier, (ours, a, b) in {"Entry": ((3500, 25), (3200, 25), (3900, 30)),
                                   "Mid": ((7500, 60), (6900, 55), (8400, 70)),
                                   "Top": ((15000, 150), (13500, 120), (17500, 180))}.items():
            for portal, (price, credits), lead_idx in [("Our Portal", ours, 1.00),
                                                       ("Competitor A", a, 0.78),
                                                       ("Competitor B", b, 0.92)]:
                p = price if portal == "Our Portal" else round(price * drift, -1)
                rows.append({"quarter": q, "portal": portal, "tier": tier, "monthly_price_aed": p,
                             "listing_credits": credits, "lead_index": lead_idx})
    return pd.DataFrame(rows)


def make_costs(account_monthly):
    rows = []
    for month in MONTHS:
        for v in ["Property", "Jobs"]:
            rows.append({"month": str(month), "vertical": v,
                         "marketing_spend": round(C.MARKETING_SPEND[v] * rng.normal(1, 0.08), -2)})
    return pd.DataFrame(rows)


def main():
    C.DATA_DIR.mkdir(exist_ok=True)
    reps, accounts, account_monthly, rep_monthly = simulate()
    rep_monthly = add_rep_revenue_and_targets(rep_monthly, account_monthly, reps)
    outputs = {"reps": reps, "accounts": accounts, "account_monthly": account_monthly,
               "rep_monthly": rep_monthly, "competitor_pricing": make_competitor_pricing(),
               "marketing_costs": make_costs(account_monthly)}
    for name, df in outputs.items():
        df.to_csv(C.DATA_DIR / f"{name}.csv", index=False)
        print(f"{name:20s} {len(df):>8,} rows")


if __name__ == "__main__":
    main()
