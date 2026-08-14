# Trade Execution Surveillance & Compliance Audit Engine

An automated compliance surveillance and data reconciliation engine designed for low-latency detection of regulatory market violations, order-to-trade reconciliation breaks, and execution volume drift.

---

## Architectural Overview

```text
[Inbound Orders Stream] ──┐
                          ├──► [Surveillance & Reconciliation Engine] ──► [Committed Trade Store]
[Market Trade Fills]   ───┘                    │
                                               └──► [Compliance Break Ledger]
                                                    ├── Dropped Fills (0 Fills)
                                                    ├── Volume Drift Discrepancies
                                                    ├── Wash Trading (Self-Matching)
                                                    └── Off-Market Price Spikes
```

**Key Capabilities**
Order-to-Trade Volume Reconciliation:

Reconciles asynchronous parent orders against downstream trade execution fills using SQL aggregation and window functions.

Isolates volume drift and flags unexecuted "dropped" fills before transaction settlement.

Temporal Wash Trading Surveillance:

Detects manipulative self-matching behavior (identical account executing opposing BUY and SELL orders for the same instrument within a 10-second window).

Off-Market Pricing Anomaly Detection:

Computes price deviations between order limit thresholds and executed trade fills, identifying anomalous slippage (>10%).

Regulatory Audit & Break Ledger:

Automatically isolates anomalies into an immutable compliance_audit_ledger while streaming diagnostic telemetry to logs/compliance_audit.log for audit readiness.

**Tech Stack**
Language: Python 3.10+

Data Processing: Pandas, NumPy

Relational Database: SQLite (In-Memory / File-based) with PostgreSQL schema parity

Audit & Logging: Python logging module, Tabular output formatters

**Project Structure**
```Plaintext
trade-surveillance-compliance-engine/
│
├── sql/
│   ├── init_schema.sql          # Relational tables (Orders, Trades, Audit Ledger)
│   └── audit_queries.sql        # Advanced analytical & self-join audit queries
│
├── src/
│   ├── __init__.py
│   ├── mock_data_generator.py   # Synthetic order/trade stream & anomaly injector
│   ├── surveillance_engine.py   # Core reconciliation & rule surveillance engine
│   └── main.py                  # End-to-end execution pipeline
│
├── logs/
│   └── compliance_audit.log     # System Activity Monitoring (SAM) audit logs
│
├── requirements.txt             # Python dependencies
├── .gitignore                   # Ignored files (logs, caches, DB files)
└── README.md                    # System documentation
```
