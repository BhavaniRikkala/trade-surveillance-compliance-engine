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
WHERE ABS(JULIANDAY(t2.execution_timestamp) - JULIANDAY(t1.execution_timestamp)) * 86400.0 <= 10.0;
