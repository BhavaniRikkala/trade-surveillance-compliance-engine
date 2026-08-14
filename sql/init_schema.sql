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
