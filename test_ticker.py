from pionex_api_template import send_pionex_request
res = send_pionex_request("GET", "/api/v1/market/tickers", params={"symbol": "BTC_USDT"})
print(res['data']['tickers'][0].keys())
