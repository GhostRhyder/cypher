from pionex_api_template import send_pionex_request
res = send_pionex_request("GET", "/api/v1/market/depth", params={"symbol": "BTC_USDT", "limit": 1})
print(res['data']['bids'][0], res['data']['asks'][0])
