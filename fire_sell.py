from pionex_api_template import send_pionex_request

COINS = ["TRX", "SOL", "ADA"]

def get_precision(symbol):
    try:
        data = send_pionex_request("GET", "/api/v1/common/symbols")
        if not data or 'data' not in data or 'symbols' not in data['data']:
             return 4
        symbols = data['data']['symbols']
        rule = next((s for s in symbols if s['symbol'] == symbol), None)
        if rule:
            return int(rule.get('basePrecision', 4))
        return 4
    except:
        return 4

def truncate(n, decimals=0):
    multiplier = 10 ** decimals
    return int(n * multiplier) / multiplier

def get_coin_balance(coin):
    try:
        data = send_pionex_request("GET", "/api/v1/account/balances")
        if data and 'data' in data and 'balances' in data['data']:
            for item in data['data']['balances']:
                if item['coin'] == coin:
                    return float(item['free'])
    except:
        pass
    return 0.0

def place_market_sell(symbol, size):
    body = {
        "symbol": symbol,
        "side": "SELL",
        "type": "MARKET",
        "size": str(size)
    }
    return send_pionex_request("POST", "/api/v1/trade/order", body=body)

def liquid_fire():
    print("🔥 LIQUIDATING POSITIONS...")
    for coin in COINS:
        symbol = f"{coin}_USDT"
        precision = get_precision(symbol)
        raw_qty = get_coin_balance(coin)
        qty = truncate(raw_qty, precision) 
        
        if qty > 0:
            print(f"\n📉 Selling {qty} {coin} (Raw: {raw_qty})...")
            resp = place_market_sell(symbol, qty)
            if resp and resp.get('result'):
                order_id = resp.get('data', {}).get('orderId', 'UNKNOWN')
                print(f"✅ SOLD: {symbol} | ID: {order_id}")
            else:
                print(f"❌ SELL FAILED: {resp}")

if __name__ == "__main__":
    liquid_fire()