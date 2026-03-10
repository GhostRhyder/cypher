import re
import json
from datetime import datetime

log_lines = open("trade_daemon_v2.log", "r").readlines()
history = []
positions = {}

re_deployed = re.compile(r"\[(2026-.*?)\] \[DEPLOYED\] Added (.*?) at ([\d\.e-]+) \(Qty: ([\d\.e-]+)\)")
re_sell = re.compile(r"\[(2026-.*?)\] \[SELL\] (.*?):.*? \(([-\+\d\.e]+)%\).*?\(Qty: ([\d\.e-]+)\)")
re_buy_execute = re.compile(r"\[(2026-.*?)\] \[EXECUTE\] ✅ BUY (.*?) for \$([\d\.e-]+) USDT")

pending_buy_cost = {}

for line in log_lines:
    if "✅ BUY " in line:
        m = re_buy_execute.search(line)
        if m:
            ts, coin, cost = m.groups()
            pending_buy_cost[coin] = float(cost)
            
    elif "[DEPLOYED]" in line:
        m = re_deployed.search(line)
        if m:
            ts, coin, entry, qty = m.groups()
            positions[coin] = {
                "entry": float(entry),
                "qty": float(qty),
                "cost_basis": pending_buy_cost.get(coin, 21.50),
                "ts": ts
            }
            
    elif "[SELL]" in line:
        m = re_sell.search(line)
        if m:
            ts, coin, pnl_pct, qty = m.groups()
            if coin in positions:
                entry = positions[coin]["entry"]
                cost_basis = positions[coin]["cost_basis"]
                pnl_pct_raw = float(pnl_pct)
                
                net_pnl_pct = pnl_pct_raw - 0.1
                pnl_usdt = cost_basis * (net_pnl_pct / 100.0)
                exit_price = entry * (1 + (pnl_pct_raw / 100.0))
                
                start_time_str = positions[coin]["ts"]
                try:
                    t1 = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
                    t2 = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                    secs = int((t2 - t1).total_seconds())
                    mins = secs // 60
                    trade_len = f"{mins}m"
                except:
                    trade_len = "N/A"
                
                history.append({
                    "timestamp": ts,
                    "direction": "LONG",
                    "trade_length": trade_len,
                    "coin": coin,
                    "entry": entry,
                    "exit": exit_price,
                    "pnl_pct": net_pnl_pct,
                    "pnl_usdt": pnl_usdt,
                    "cost_basis": cost_basis,
                    "result": "WIN" if net_pnl_pct >= 0 else "LOSS"
                })
                del positions[coin]

print(f"Recovered {len(history)} trades.")
# Dump to history.json natively reversing it or keeping chronological? The daemon loads chronological (oldest first) and reverses for UI.
# So history.json must be chronological (oldest first).
with open("history_recovered.json", "w") as f:
    json.dump(history, f, indent=2)

