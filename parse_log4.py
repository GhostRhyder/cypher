import json

with open("history.json", "r") as f:
    history = json.load(f)

for t in history:
    # Use entry and exit to find raw PNL
    entry = float(t['entry'])
    exit_p = float(t['exit'])
    
    raw_pnl_pct = (exit_p - entry) / entry * 100.0
    
    net_pnl_pct = raw_pnl_pct - 0.2
    cb = float(t.get('cost_basis', 21.50))
    
    t['pnl_pct'] = net_pnl_pct
    t['pnl_usdt'] = cb * (net_pnl_pct / 100.0)
    t['result'] = "WIN" if net_pnl_pct >= 0 else "LOSS"

with open("history.json", "w") as f:
    json.dump(history, f, indent=2)

print(f"Reprocessed {len(history)} trades with 0.2% fee.")
total = sum(t['pnl_usdt'] for t in history)
print(f"Total PNL is now: {total:.2f}")

