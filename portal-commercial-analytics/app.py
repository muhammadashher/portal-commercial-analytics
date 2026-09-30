"""Self-service commercial dashboard. Run:  streamlit run app.py"""
import json

import pandas as pd
import plotly.express as px
import streamlit as st

import config as C

st.set_page_config(page_title="Portal Commercial Analytics", page_icon="📈", layout="wide")


@st.cache_data
def load(name):
    return pd.read_csv(C.OUT_DIR / f"{name}.csv")


if not (C.OUT_DIR / "metrics.json").exists():
    st.error("Outputs not found. Run `python pipeline.py` first.")
    st.stop()

metrics = json.loads((C.OUT_DIR / "metrics.json").read_text())
kpis = load("monthly_kpis")
att = load("target_attainment")
funnel = load("sales_funnel")
ret = load("revenue_retention")
watch = load("churn_watchlist")
ups = load("upsell_opportunities_sized")
disc = load("discount_effectiveness")
pnl = load("pnl_by_vertical")
price = load("pricing_benchmark")
q4 = load("q4_2026_rep_targets")
bt = load("target_backtest_q3_2026")

st.title("Property & Jobs: Commercial Performance")
st.caption("Synthetic data mimicking a UAE classifieds portal, Oct 2024 - Sep 2026. Competitor data is illustrative.")

vertical = st.sidebar.radio("Vertical", ["Property", "Jobs"])
st.sidebar.markdown("Data refreshes when `python pipeline.py` is re-run.")

k = kpis[kpis.vertical == vertical]
latest = k.iloc[-1]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Revenue (Sep 2026)", f"AED {latest.revenue / 1e6:.2f}M", f"{latest.yoy_growth:.1%} YoY")
c2.metric("Active accounts", f"{int(latest.active_accounts):,}")
c3.metric("ARPA", f"AED {latest.arpa:,.0f}")
c4.metric("12m NRR", f"{metrics['nrr_12m'][vertical]:.1%}")
c5.metric("Contribution margin (12m)", f"{metrics['contribution_margin_12m'][vertical]:.1%}")

tabs = st.tabs(["Overview", "Targets", "Sales productivity", "Account health", "P&L", "Pricing"])

with tabs[0]:
    st.plotly_chart(px.bar(k, x="month", y="revenue", title="Monthly revenue (AED)"), width="stretch")
    col1, col2 = st.columns(2)
    col1.plotly_chart(px.line(k, x="month", y="logo_churn_rate", title="Monthly logo churn"), width="stretch")
    r = ret[ret.vertical == vertical].melt(id_vars="month", value_vars=["nrr", "grr"])
    col2.plotly_chart(px.line(r, x="month", y="value", color="variable", title="12-month NRR / GRR"),
                      width="stretch")

with tabs[1]:
    b = metrics["target_backtest"]
    st.subheader("Q3 2026 backtest: legacy equal split vs bottom-up model")
    s1, s2, s3 = st.columns(3)
    s1.metric("Attainment std dev", f"{b['bottom_up']['attainment_std']:.3f}",
              f"{b['bottom_up']['attainment_std'] - b['legacy']['attainment_std']:+.3f}", delta_color="inverse")
    s2.metric("Reps within ±10%", f"{b['bottom_up']['within_10pct']:.0%}",
              f"{b['bottom_up']['within_10pct'] - b['legacy']['within_10pct']:+.0%}")
    s3.metric("Target error (MAPE)", f"{b['bottom_up']['mape']:.1%}",
              f"{b['bottom_up']['mape'] - b['legacy']['mape']:+.1%}", delta_color="inverse")
    btv = bt[bt.vertical == vertical].melt(id_vars="rep_id", value_vars=["legacy_attainment", "bottom_up_attainment"])
    fig = px.bar(btv, x="rep_id", y="value", color="variable", barmode="group", title="Q3 attainment by rep")
    fig.add_hline(y=1.0, line_dash="dash")
    st.plotly_chart(fig, width="stretch")
    st.subheader("Q4 2026 monthly targets")
    st.dataframe(q4[q4.vertical == vertical][["rep_id", "base_book", "trailing_churn", "new_rate",
                                              "target_oct", "target_nov", "target_dec", "target_q"]],
                 width="stretch", hide_index=True)
    a = att[att.vertical == vertical]
    st.plotly_chart(px.line(a, x="month", y="attainment_3m_avg", color="rep_id",
                            title="Legacy target attainment, 3-month rolling"), width="stretch")

with tabs[2]:
    f = funnel[funnel.vertical == vertical]
    st.plotly_chart(px.scatter(f, x="call_to_meeting", y="meeting_to_deal", size="new_business_revenue",
                               color="productivity_quartile", hover_name="rep_id",
                               title="Rep funnel efficiency (last 6 months)"), width="stretch")
    st.dataframe(f, width="stretch", hide_index=True)

with tabs[3]:
    w = watch[watch.vertical == vertical]
    st.subheader(f"Churn watchlist: {len(w)} accounts, AED {w.revenue.sum():,.0f}/month at risk")
    st.dataframe(w, width="stretch", hide_index=True)
    u = ups[ups.vertical == vertical]
    st.subheader(f"Upsell opportunities: {len(u)} accounts, AED {u.uplift_monthly.sum():,.0f}/month uplift")
    st.dataframe(u, width="stretch", hide_index=True)
    d = disc[disc.vertical == vertical]
    st.plotly_chart(px.bar(d, x="discount_band", y="monthly_churn_rate", title="Churn by discount band"),
                    width="stretch")

with tabs[4]:
    p = pnl[pnl.vertical == vertical]
    cost_cols = ["payment_fees", "tech_allocation", "sales_team_cost", "commissions", "marketing_spend"]
    st.plotly_chart(px.bar(p, x="month", y=cost_cols + ["contribution"], title="Revenue split: costs and contribution"),
                    width="stretch")
    st.plotly_chart(px.line(p, x="month", y="contribution_margin", title="Contribution margin"),
                    width="stretch")

with tabs[5]:
    if vertical == "Jobs":
        st.info("The pricing benchmark covers the Property vertical.")
    st.plotly_chart(px.bar(price, x="tier", y="cost_per_lead_aed", color="portal", barmode="group",
                           title="Cost per lead by package tier, Q3 2026 (illustrative)"), width="stretch")
    st.dataframe(price, width="stretch", hide_index=True)
