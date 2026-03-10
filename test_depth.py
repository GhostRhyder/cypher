from pionex_api_template import send_pionex_request
res = send_pionex_request("GET", "/api/v1/market/depth", params={"symbol": "BTC_USDT", "limit": 5})
if res and 'data' in res: print("Depth works:", res['data'].keys())
else: print("Depth failed:", res)
