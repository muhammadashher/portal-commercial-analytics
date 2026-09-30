"""Central configuration for the Portal Commercial Analytics project.

All data is synthetic and generated from the assumptions below. Prices and
competitor figures are illustrative, not real Bayut / dubizzle / competitor data.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "outputs"
REPORT_DIR = ROOT / "reports"
SQL_DIR = ROOT / "sql"
DB_PATH = DATA_DIR / "portal.db"

SEED = 42
START_MONTH = "2024-10"
N_MONTHS = 24                      # Oct 2024 - Sep 2026

# ---------------------------------------------------------------- Property vertical
PROPERTY_REPS = 12
PROPERTY_START_ACCOUNTS = 300
PROPERTY_PACKAGES = {              # monthly list price (AED), listing credits
    "Basic":    {"price": 3500,  "credits": 25},
    "Standard": {"price": 7500,  "credits": 60},
    "Premium":  {"price": 15000, "credits": 150},
}
FEATURED_ADDON_PRICE = 150         # AED per featured-listing boost
DUBAI_AREAS = {                    # relative lead demand per listing
    "Dubai Marina": 1.25, "Downtown Dubai": 1.30, "Business Bay": 1.10,
    "Jumeirah Village Circle": 1.15, "Palm Jumeirah": 1.05, "Dubai Hills Estate": 1.20,
    "Jumeirah Lake Towers": 1.00, "Al Barsha": 0.90, "Deira": 0.80, "Arabian Ranches": 0.95,
}

# ---------------------------------------------------------------- Jobs vertical
JOBS_REPS = 6
JOBS_START_ACCOUNTS = 400
JOBS_PACKAGES = {                  # monthly price (AED), included job slots (None = pay per post)
    "Pay-per-Post": {"price": 499,  "slots": None},
    "Pack-5":       {"price": 1999, "slots": 5},
    "Unlimited":    {"price": 4999, "slots": 25},
}
JOB_SECTORS = {                    # relative applications per post
    "Hospitality": 1.30, "Retail": 1.20, "Real Estate": 1.00, "Technology": 0.85,
    "Healthcare": 0.90, "Construction": 1.10, "Finance": 0.80, "Logistics": 1.05,
}

# ---------------------------------------------------------------- Seasonality (UAE)
PROPERTY_SEASONALITY = {1: 1.08, 2: 1.06, 3: 1.04, 4: 1.00, 5: 0.96, 6: 0.91,
                        7: 0.85, 8: 0.86, 9: 0.95, 10: 1.05, 11: 1.09, 12: 1.04}
JOBS_SEASONALITY = {1: 1.10, 2: 1.06, 3: 0.97, 4: 1.00, 5: 0.98, 6: 0.90,
                    7: 0.84, 8: 0.88, 9: 1.07, 10: 1.08, 11: 1.03, 12: 0.92}

# ---------------------------------------------------------------- Cost base (P&L)
REP_MONTHLY_COST = 14000           # salary + allowances per inside sales rep (AED)
COMMISSION_RATE = 0.10             # on new-business + upsell revenue
PAYMENT_FEE_RATE = 0.025
TECH_ALLOCATION_RATE = 0.18        # share of revenue allocated for platform costs
MARKETING_SPEND = {"Property": 330000, "Jobs": 95000}   # average AED per month

# ---------------------------------------------------------------- Targets
LEGACY_TARGET_GROWTH = 0.12        # legacy method: last quarter x 1.12, split equally
Q4_2026_GROWTH_GOAL = 0.10         # company goal for Oct-Dec 2026 vs Jul-Sep 2026
