"""Run the full pipeline: generate data -> SQLite -> SQL + Python analysis -> Excel model."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import analysis        # noqa: E402
import build_db        # noqa: E402
import excel_model     # noqa: E402
import generate_data   # noqa: E402

if __name__ == "__main__":
    print("1/4 Generating synthetic portal data ...")
    generate_data.main()
    print("2/4 Building SQLite database ...")
    build_db.main()
    print("3/4 Running SQL and Python analysis ...")
    analysis.main()
    print("4/4 Building Excel target & P&L model ...")
    excel_model.main()
    print("Done. Findings: reports/findings.md | Dashboard: streamlit run app.py")
