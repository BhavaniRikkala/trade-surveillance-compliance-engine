import sqlite3
import random
from datetime import datetime, timedelta

def populate_mock_market_data(conn: sqlite3.Connection):
    """
    Generates synthetic orders and trade executions, injecting intentional
    compliance violations and reconciliation breaks for surveillance testing.
    """
    cursor = conn.cursor()
    base_time = datetime(2026, 8, 14, 9, 30, 0)
    
    symbols = ['AAPL', 'MSFT', 'GS', 'NVDA', 'JPM']
    accounts = ['ACC_1001', 'ACC_1002', 'ACC_1003', 'ACC_BAD_ACTOR']
    
    orders = []
    executions = []
    
    # 1. Clean/Compliant Orders and Executions
    for i in range(1, 11):
        order_id = f"ORD_{i:04d}"
        account = random.choice(accounts[:3])
        sym = random.choice(symbols)
        side = random.choice(['BUY', 'SELL'])
        qty = random.choice([100, 200, 500, 1000])
        price = round(random.uniform(150.0, 450.0), 2)
        ts = base_time + timedelta(seconds=i * 15)
        
        orders.append((order_id, account, sym, side, qty, price, ts.strftime('%Y-%m-%d %H:%M:%S')))
        
        # Perfect Fill
        trade_id = f"TRD_{i:04d}"
        exec_ts = ts + timedelta(milliseconds=random.randint(50, 200))
        executions.append((trade_id, order_id, account, sym, side, qty, price, exec_ts.strftime('%Y-%m-%d %H:%M:%S')))

    # 2. Inject Anomaly 1: Dropped Trade Fill (Order without Trade)
    orders.append(('ORD_9901', 'ACC_1001', 'GS', 'BUY', 500, 410.00, (base_time + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')))

    # 3. Inject Anomaly 2: Quantity Mismatch Drift
    orders.append(('ORD_9902', 'ACC_1002', 'AAPL', 'SELL', 1000, 220.00, (base_time + timedelta(minutes=6)).strftime('%Y-%m-%d %H:%M:%S')))
    executions.append(('TRD_9902', 'ORD_9902', 'ACC_1002', 'AAPL', 'SELL', 600, 220.00, (base_time + timedelta(minutes=6, seconds=1)).strftime('%Y-%m-%d %H:%M:%S')))

    # 4. Inject Anomaly 3: Wash Trading (Rapid BUY and SELL by same account within 2s)
    wash_ts_buy = base_time + timedelta(minutes=10)
    wash_ts_sell = wash_ts_buy + timedelta(seconds=2)
    orders.append(('ORD_9903_B', 'ACC_BAD_ACTOR', 'NVDA', 'BUY', 2000, 120.00, wash_ts_buy.strftime('%Y-%m-%d %H:%M:%S')))
    orders.append(('ORD_9903_S', 'ACC_BAD_ACTOR', 'NVDA', 'SELL', 2000, 120.00, wash_ts_sell.strftime('%Y-%m-%d %H:%M:%S')))
    
    executions.append(('TRD_9903_B', 'ORD_9903_B', 'ACC_BAD_ACTOR', 'NVDA', 'BUY', 2000, 120.00, (wash_ts_buy + timedelta(milliseconds=100)).strftime('%Y-%m-%d %H:%M:%S')))
    executions.append(('TRD_9903_S', 'ORD_9903_S', 'ACC_BAD_ACTOR', 'NVDA', 'SELL', 2000, 120.00, (wash_ts_sell + timedelta(milliseconds=100)).strftime('%Y-%m-%d %H:%M:%S')))

    # 5. Inject Anomaly 4: Off-Market Price Outlier (>15% price spike)
    orders.append(('ORD_9904', 'ACC_1003', 'MSFT', 'BUY', 100, 420.00, (base_time + timedelta(minutes=12)).strftime('%Y-%m-%d %H:%M:%S')))
    executions.append(('TRD_9904', 'ORD_9904', 'ACC_1003', 'MSFT', 'BUY', 100, 550.00, (base_time + timedelta(minutes=12, seconds=1)).strftime('%Y-%m-%d %H:%M:%S')))

    cursor.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)", orders)
    cursor.executemany("INSERT INTO trade_executions VALUES (?, ?, ?, ?, ?, ?, ?, ?)", executions)
    conn.commit()
5.Create src/surveillance_engine.py:Type 'src/surveillance_engine.py' in the filename box.Paste the following code and commit:Pythonimport sqlite3
import pandas as pd
import logging

class ComplianceSurveillanceEngine:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.logger = logging.getLogger("ComplianceSurveillance")

    def run_order_to_trade_reconciliation(self):
        """Validates that all executed volumes match initial orders with zero record loss."""
        self.logger.info("Executing Order-to-Trade Volume Reconciliation...")
        
        query = """
        SELECT 
            o.order_id,
            o.account_id,
            o.symbol,
            o.order_quantity,
            COALESCE(SUM(t.executed_quantity), 0) AS total_executed_quantity
        FROM orders o
        LEFT JOIN trade_executions t ON o.order_id = t.order_id
        GROUP BY o.order_id, o.account_id, o.symbol, o.order_quantity
        """
        df = pd.read_sql(query, self.conn)
        
        for _, row in df.iterrows():
            ordered = row['order_quantity']
            executed = row['total_executed_quantity']
            
            if executed == 0:
                self._record_violation(
                    incident_type="DROPPED_FILL_BREAK",
                    severity="HIGH",
                    account_id=row['account_id'],
                    symbol=row['symbol'],
                    order_id=row['order_id'],
                    trade_id=None,
                    details=f"Order {row['order_id']} placed for {ordered} shares but 0 fills recorded in trade ledger."
                )
            elif ordered != executed:
                self._record_violation(
                    incident_type="VOLUME_DRIFT_MISMATCH",
                    severity="MEDIUM",
                    account_id=row['account_id'],
                    symbol=row['symbol'],
                    order_id=row['order_id'],
                    trade_id=None,
                    details=f"Order quantity ({ordered}) does not match executed total ({executed}). Drift: {ordered - executed} units."
                )

    def run_wash_trading_surveillance(self, time_window_seconds: float = 10.0):
        """Identifies wash trades: same account buying and selling the same instrument within a brief window."""
        self.logger.info("Running Wash Trading Pattern Surveillance...")
        
        query = f"""
        SELECT 
            t1.account_id,
            t1.symbol,
            t1.trade_id AS buy_trade_id,
            t2.trade_id AS sell_trade_id,
            t1.order_id AS buy_order_id,
            t2.order_id AS sell_order_id,
            t1.execution_timestamp AS buy_time,
            t2.execution_timestamp AS sell_time,
            ROUND(ABS(JULIANDAY(t2.execution_timestamp) - JULIANDAY(t1.execution_timestamp)) * 86400.0, 2) AS duration_seconds
        FROM trade_executions t1
        JOIN trade_executions t2 
            ON t1.account_id = t2.account_id 
            AND t1.symbol = t2.symbol 
            AND t1.side = 'BUY' 
            AND t2.side = 'SELL'
            AND t1.trade_id != t2.trade_id
        WHERE ABS(JULIANDAY(t2.execution_timestamp) - JULIANDAY(t1.execution_timestamp)) * 86400.0 <= {time_window_seconds}
        """
        df = pd.read_sql(query, self.conn)
        
        for _, row in df.iterrows():
            self._record_violation(
                incident_type="WASH_TRADE_DETECTED",
                severity="CRITICAL",
                account_id=row['account_id'],
                symbol=row['symbol'],
                order_id=f"{row['buy_order_id']},{row['sell_order_id']}",
                trade_id=f"{row['buy_trade_id']},{row['sell_trade_id']}",
                details=f"Self-matching execution pattern on {row['symbol']} within {row['duration_seconds']}s window."
            )

    def run_off_market_pricing_surveillance(self, threshold_pct: float = 0.10):
        """Detects executions that deviate significantly from the order limit price."""
        self.logger.info("Running Execution Price Deviation Checks...")
        
        query = """
        SELECT 
            t.trade_id,
            t.order_id,
            t.account_id,
            t.symbol,
            o.limit_price,
            t.execution_price,
            ABS(t.execution_price - o.limit_price) / o.limit_price AS price_deviation
        FROM trade_executions t
        JOIN orders o ON t.order_id = o.order_id
        """
        df = pd.read_sql(query, self.conn)
        outliers = df[df['price_deviation'] > threshold_pct]
        
        for _, row in outliers.iterrows():
            dev_percent = round(row['price_deviation'] * 100, 2)
            self._record_violation(
                incident_type="OFF_MARKET_PRICE_SPIKE",
                severity="HIGH",
                account_id=row['account_id'],
                symbol=row['symbol'],
                order_id=row['order_id'],
                trade_id=row['trade_id'],
                details=f"Execution price ({row['execution_price']}) deviated by {dev_percent}% from limit price ({row['limit_price']})."
            )

    def _record_violation(self, incident_type, severity, account_id, symbol, order_id, trade_id, details):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO compliance_audit_ledger 
            (incident_type, severity, account_id, symbol, order_id, trade_id, violation_details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (incident_type, severity, account_id, symbol, order_id, trade_id, details))
        self.conn.commit()
        self.logger.warning(f"[{severity}] {incident_type} | Account: {account_id} | Details: {details}")
