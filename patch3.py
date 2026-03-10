with open('/root/.openclaw/workspace/cypher_swing.py', 'r') as f:
    code = f.read()

code = code.replace("res = get_candles(symbol, \"4H\", limit)", "res = get_candles(symbol, \"4h\", limit)")

with open('/root/.openclaw/workspace/cypher_swing.py', 'w') as f:
    f.write(code)
