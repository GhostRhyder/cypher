with open('/root/.openclaw/workspace/cypher_swing.py', 'r') as f:
    code = f.read()

old_str1 = "from pionex_api_swing import send_pionex_request, get_candles"
new_str1 = "from binance_api_swing import send_binance_request as send_pionex_request, get_candles"
code = code.replace(old_str1, new_str1)

old_str2 = "item['coin']"
new_str2 = "item.get('coin', item.get('asset'))"
code = code.replace(old_str2, new_str2)

with open('/root/.openclaw/workspace/cypher_swing.py', 'w') as f:
    f.write(code)
