with open('/root/.openclaw/workspace/cypher_swing.py', 'r') as f:
    code = f.read()

code = code.replace('send_pionex_request("GET", "/api/v1/account/balances")', 'send_pionex_request("GET", "/api/v3/account")')
code = code.replace('send_pionex_request("GET", "/api/v1/market/tickers", params={"symbol": symbol})', 'send_pionex_request("GET", "/api/v3/ticker/price", params={"symbol": symbol.replace("_", "")})')
code = code.replace("res['data']['tickers'][0]['close']", "res['data']['price']")
code = code.replace('send_pionex_request("POST", "/api/v1/trade/order", body=body)', 'send_pionex_request("POST", "/api/v3/order", params={"symbol": symbol.replace("_", ""), "side": "BUY", "type": "MARKET", "quoteOrderQty": usdc_amount})')

with open('/root/.openclaw/workspace/cypher_swing.py', 'w') as f:
    f.write(code)
