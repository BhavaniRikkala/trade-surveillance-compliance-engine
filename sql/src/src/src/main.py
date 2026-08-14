import sqlite3
import os
import sys
import logging
import pandas as pd

# Ensure the script resolves sibling modules correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mock_data_generator import populate_mock_market_data
from surveillance_engine import ComplianceSurveillanceEngine

def setup_logger():
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | [%(levelname)s] | %(message)s',
        handlers=[
            logging.FileHandler("logs/compliance_audit.log"),
            logging.StreamHandler()
        ]
    )

def main():
    setup_logger()
    logging.info("Starting Trade Execution Surveillance & Compliance Engine...")

    # 1. Initialize In-Memory Database
    conn = sqlite3.connect(":memory:")
    
    # 2. Apply Schemas
    schema_path = os.path.join(os.path.dirname(__file__), "..", "sql", "init_schema.sql")
    with open(schema_path, "r") as f:
        conn.executescript(f.read())
    logging.info("Database schema initialized successfully.")

    # 3. Populate Synthetic Market Order & Trade Feeds
    populate_mock_market_data(conn)
    logging.info("Synthetic market feed loaded into pipeline.")

    # 4. Run Surveillance Engine Modules
    engine = ComplianceSurveillanceEngine(conn)
    engine.run_order_to_trade_reconciliation()
    engine.run_wash_trading_surveillance(time_window_seconds=10.0)
    engine.run_off_market_pricing_surveillance(threshold_pct=0.10)

    # 5. Output Summary Report Table
    print("\n" + "="*80)
    print("COMPLIANCE AUDIT & SURVEILLANCE REPORT")
    print("="*80)
    
    audit_df = pd.read_sql("""
        SELECT violation_id, incident_type, severity, account_id, symbol, violation_details 
        FROM compliance_audit_ledger
    """, conn)
    
    if not audit_df.empty:
        print(audit_df.to_markdown(index=False))
    else:
        print("No compliance violations detected.")
    print("="*80 + "\n")
    logging.info("Surveillance cycle completed. Audit records persisted to ledger.")

if __name__ == "__main__":
    main()
