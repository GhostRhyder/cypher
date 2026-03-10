with open('/root/.openclaw/workspace/trade_daemon_v2.py', 'r') as f:
    code = f.read()

old_str = "usdt = max(0.0, get_usdt_balance() - 60.0)  # Reserve $60 for Swing Daemon"
new_str = "usdt = get_usdt_balance()"
code = code.replace(old_str, new_str)

with open('/root/.openclaw/workspace/trade_daemon_v2.py', 'w') as f:
    f.write(code)
