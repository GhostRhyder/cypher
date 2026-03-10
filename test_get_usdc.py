from binance_api_swing import send_binance_request
def get_usdc_balance() -> float:
    try:
        res = send_binance_request("GET", "/api/v3/account")
        print("res:", res.keys() if isinstance(res, dict) else res)
        for item in res['data']['balances']:
            if item.get('coin', item.get('asset')) == 'USDC':
                return float(item['free'])
        return 0.0
    except Exception as e:
        print("err:", e)
        return 0.0

print(get_usdc_balance())
