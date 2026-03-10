from pionex_api_template import send_pionex_request

res = send_pionex_request("GET", "/api/v1/account/balances")
if not res or 'data' not in res:
    print("API Error:", res)
    exit()
    
balances = res['data']['balances']

total_usdt_value = 0.0

print("--- Current Portfolio Breakdown ---")
for b in balances:
    coin = b['coin']
    free = float(b['free'])
    if free <= 0:
        continue
        
    if coin == 'USDT':
        total_usdt_value += free
        print(f"USDT: ${free:.2f}")
    else:
        symbol = f"{coin}_USDT"
        try:
            ticker_res = send_pionex_request("GET", "/api/v1/market/tickers", params={"symbol": symbol})
            if ticker_res and 'data' in ticker_res:
                price = float(ticker_res['data']['tickers'][0]['close'])
                val = free * price
                total_usdt_value += val
                if val > 0.1:
                    print(f"{coin}: {free} x ${price} = ${val:.2f}")
        except Exception as e:
            pass

print(f"\nTOTAL ACCOUNT ESTIMATED VALUE: ${total_usdt_value:.2f}")
