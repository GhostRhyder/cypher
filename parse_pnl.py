import json

with open("history.json", "r") as f:
    history = json.load(f)

total_pnl = 0
for t in history:
    pnl = t.get("pnl_usdt")
    if pnl is None:
        pnl = t.get("cost_basis", 21.50) * (t.get("pnl_pct", 0) / 100.0)
    total_pnl += pnl

print(f"Total PNL of {len(history)} trades in history.json: {total_pnl:.2f}")

