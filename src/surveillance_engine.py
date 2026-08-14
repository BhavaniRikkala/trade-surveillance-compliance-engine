import sqlite3
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
