import re
import json
from datetime import datetime

log_lines = open("trade_daemon_v2.log", "r").readlines()
recovered = []
positions = {}

re_deployed = re.compile(r"\[(2026-.*?)\] \[DEPLOYED\] Added (.*?) at ([\d\.e-]+) \(Qty: ([\d\.e-]+)\)")
re_sell = re.compile(r"\[(2026-.*?)\] \[SELL\] (.*?):.*?\((.*?%)\).*?\(Qty: ([\d\.e-]+)\)")
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
            ts, coin, pnl_str, qty = m.groups()
            if coin in positions:
                entry = positions[coin]["entry"]
                cost_basis = positions[coin]["cost_basis"]
                
                # Extract number from pnl_str e.g. "Peak: 1.74%" or "-0.90%"
                pnl_str = pnl_str.replace("Peak:", "").replace("+", "").replace("%", "").strip()
                try:
                    pnl_pct_raw = float(pnl_str)
                except:
                    pnl_pct_raw = 0.0
                
                # Deduct 0.2% round-trip market fee
                net_pnl_pct = pnl_pct_raw - 0.2
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
                
                recovered.append({
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

print(f"Total recovered from log: {len(recovered)}")

with open("history_recovered.json", "r") as f:
    current_history = json.load(f)

# Use original history elements and apply 0.2% fee, UNLESS it's already in recovered
history_dict = {}

for t in current_history:
    key = f"{t['timestamp']}_{t['coin']}"
    # Raw pnl wasn't stored, but we can back it out:
    # t['pnl_pct'] currently has NO fee deduction (wait, earlier I did -0.1).
    # actually, `history_recovered.json` hasn't been modified yet, it was just written. Let me just use `history.json` which originally had 50 trades without fee deduction. 
    # But wait, I overwrote `history.json` with my previous script!
    # Let me restore `history.json` from a backup or recalculate.
    # Ah, I don't need to. I'll just use the entry and exit prices to recalculate!
    
    entry = float(t['entry'])
    exit_p = float(t['exit'])
    raw_pnl_pct = (exit_p - entry) / entry * 100.0
    
    net_pnl_pct = raw_pnl_pct - 0.2
    cb = t.get('cost_basis', 21.50)
    
    t['pnl_pct'] = net_pnl_pct
    t['pnl_usdt'] = cb * (net_pnl_pct / 100.0)
    t['result'] = "WIN" if net_pnl_pct >= 0 else "LOSS"
    
    history_dict[key] = t

for t in recovered:
    key = f"{t['timestamp']}_{t['coin']}"
    if key not in history_dict:
        history_dict[key] = t

# Sort chronologically (oldest first)
final_history = sorted(list(history_dict.values()), key=lambda x: x['timestamp'])

with open("history.json", "w") as f:
    json.dump(final_history, f, indent=2)

print(f"Final history size: {len(final_history)}")

