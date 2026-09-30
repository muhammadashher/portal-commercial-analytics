"""Sanity tests. Run: pytest -q (after python pipeline.py)."""
import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import config as C  # noqa: E402
from analysis import allocate, bottom_up_expectation  # noqa: E402


def load(name):
    return pd.read_csv(C.DATA_DIR / f"{name}.csv")


def test_no_duplicate_account_months():
    am = load("account_monthly")
    assert not am.duplicated(["account_id", "month"]).any()


def test_revenue_positive_and_discount_bounded():
    am = load("account_monthly")
    assert (am["revenue"] > 0).all()
    assert am["discount_pct"].between(0, 0.25).all()


def test_churned_accounts_do_not_return():
    am = load("account_monthly").sort_values(["account_id", "month"])
    last = am.groupby("account_id")["month"].max()
    churn_month = am[am.churned == 1].set_index("account_id")["month"]
    assert (last.loc[churn_month.index] == churn_month).all()


def test_rep_book_matches_account_revenue():
    am, rm = load("account_monthly"), load("rep_monthly")
    a = am.groupby(["rep_id", "month"])["revenue"].sum()
    r = rm.set_index(["rep_id", "month"])["book_revenue"]
    assert (a.reindex(r.index).fillna(0) - r).abs().max() < 1


def test_targets_sum_to_goal():
    con = sqlite3.connect(C.DB_PATH)
    am = pd.read_sql("SELECT * FROM account_monthly", con)
    rm = pd.read_sql("SELECT * FROM rep_monthly", con)
    goal = pd.Series({"Property": 1_000_000.0, "Jobs": 250_000.0})
    t = allocate(bottom_up_expectation(rm, am, "2026-09"), goal)
    assert abs(t.groupby("vertical")["target_q"].sum() - goal).max() < 1e-6
    months = t[["target_m1", "target_m2", "target_m3"]].sum(axis=1)
    assert (months - t["target_q"]).abs().max() < 1e-6


def test_bottom_up_beats_legacy_in_backtest():
    m = json.loads((C.OUT_DIR / "metrics.json").read_text())
    bt = m["target_backtest"]
    assert bt["bottom_up"]["mape"] < bt["legacy"]["mape"]
    assert bt["bottom_up"]["attainment_std"] < bt["legacy"]["attainment_std"]
