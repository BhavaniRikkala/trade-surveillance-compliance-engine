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
