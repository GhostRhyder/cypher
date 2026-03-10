import json

# 1. Update history.json
try:
    with open("history.json", "r") as f:
        history = json.load(f)
    for trade in history:
        if "version" not in trade:
            trade["version"] = "V2"
    with open("history.json", "w") as f:
        json.dump(history, f, indent=2)
    print("history.json updated")
except Exception as e:
    print(e)

# 2. Update trade_daemon_v2.py
with open("trade_daemon_v2.py", "r") as f:
    code = f.read()

old_trade = '''    trade = {
        "timestamp": now_plus_one.strftime("%Y-%m-%d %H:%M:%S"),
        "direction": "LONG",
        "trade_length": trade_len,
        "coin": coin,
        "entry": entry,
        "exit": exit_price,
        "pnl_pct": pnl_pct_net,
        "pnl_usdt": pnl_usdt,
        "cost_basis": cost_basis,
        "result": "WIN" if pnl_pct_net >= 0 else "LOSS"
    }'''

new_trade = '''    trade = {
        "timestamp": now_plus_one.strftime("%Y-%m-%d %H:%M:%S"),
        "version": "V3",
        "direction": "LONG",
        "trade_length": trade_len,
        "coin": coin,
        "entry": entry,
        "exit": exit_price,
        "pnl_pct": pnl_pct_net,
        "pnl_usdt": pnl_usdt,
        "cost_basis": cost_basis,
        "result": "WIN" if pnl_pct_net >= 0 else "LOSS"
    }'''

if old_trade in code:
    code = code.replace(old_trade, new_trade)
    with open("trade_daemon_v2.py", "w") as f:
        f.write(code)
    print("trade_daemon_v2.py updated")
else:
    print("trade_daemon_v2.py not replaced!")

