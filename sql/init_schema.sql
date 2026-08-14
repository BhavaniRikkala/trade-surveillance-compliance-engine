-- 1. Inbound Order Intent Table
CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(50) PRIMARY KEY,
    account_id VARCHAR(20) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(4) CHECK (side IN ('BUY', 'SELL')),
    order_quantity INT NOT NULL,
    limit_price DECIMAL(15, 2) NOT NULL,
    order_timestamp TIMESTAMP NOT NULL
);

-- 2. Market Execution / Trade Fill Table
CREATE TABLE IF NOT EXISTS trade_executions (
    trade_id VARCHAR(50) PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL,
    account_id VARCHAR(20) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(4) CHECK (side IN ('BUY', 'SELL')),
    executed_quantity INT NOT NULL,
    execution_price DECIMAL(15, 2) NOT NULL,
    execution_timestamp TIMESTAMP NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- 3. Compliance Violation & Audit Break Ledger
CREATE TABLE IF NOT EXISTS compliance_audit_ledger (
    violation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_type VARCHAR(50) NOT NULL,
    severity VARCHAR(10) CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    account_id VARCHAR(20),
    symbol VARCHAR(10),
    order_id VARCHAR(50),
    trade_id VARCHAR(50),
    violation_details TEXT NOT NULL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
2.Create sql/audit_queries.sql:Type 'sql/audit_queries.sql' in the filename box.Paste the following code and commit:SQL-- Query 1: Order vs. Execution Reconciliation (Volume Drift & Dropped Records)
SELECT 
    o.order_id,
    o.account_id,
    o.symbol,
    o.order_quantity,
    COALESCE(SUM(t.executed_quantity), 0) AS total_executed_quantity,
    (o.order_quantity - COALESCE(SUM(t.executed_quantity), 0)) AS quantity_drift,
    CASE 
        WHEN SUM(t.executed_quantity) IS NULL THEN 'DROPPED_FILL'
        WHEN SUM(t.executed_quantity) != o.order_quantity THEN 'QUANTITY_MISMATCH'
        ELSE 'RECONCILED'
    END AS reconciliation_status
FROM orders o
LEFT JOIN trade_executions t ON o.order_id = t.order_id
GROUP BY o.order_id, o.account_id, o.symbol, o.order_quantity;

-- Query 2: Wash Trading Detection via Temporal Self-Joins
SELECT 
    t1.account_id,
    t1.symbol,
    t1.trade_id AS buy_trade_id,
    t2.trade_id AS sell_trade_id,
    t1.execution_timestamp AS buy_time,
    t2.execution_timestamp AS sell_time,
    ABS(JULIANDAY(t2.execution_timestamp) - JULIANDAY(t1.execution_timestamp)) * 86400.0 AS duration_seconds
FROM trade_executions t1
JOIN trade_executions t2 
    ON t1.account_id = t2.account_id 
    AND t1.symbol = t2.symbol 
    AND t1.side = 'BUY' 
    AND t2.side = 'SELL'
    AND t1.trade_id != t2.trade_id
WHERE ABS(JULIANDAY(t2.execution_timestamp) - JULIANDAY(t1.execution_timestamp))
