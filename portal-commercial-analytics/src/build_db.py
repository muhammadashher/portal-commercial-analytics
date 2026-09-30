"""Load the generated CSV files into a SQLite database (data/portal.db)."""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

TABLES = ["reps", "accounts", "account_monthly", "rep_monthly", "competitor_pricing", "marketing_costs"]


def main():
    if C.DB_PATH.exists():
        C.DB_PATH.unlink()
    with sqlite3.connect(C.DB_PATH) as con:
        for t in TABLES:
            df = pd.read_csv(C.DATA_DIR / f"{t}.csv")
            df.to_sql(t, con, index=False)
        con.execute("CREATE INDEX idx_am_acc_month ON account_monthly(account_id, month)")
        con.execute("CREATE INDEX idx_am_vert_month ON account_monthly(vertical, month)")
        con.execute("CREATE INDEX idx_rm_rep_month ON rep_monthly(rep_id, month)")
    print(f"SQLite database written to {C.DB_PATH}")


if __name__ == "__main__":
    main()
