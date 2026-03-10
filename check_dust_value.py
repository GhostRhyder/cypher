import requests
import json

try:
    # Get current prices for all dust
    data = requests.get('http://127.0.0.1:8080/api/data').json()
    balances = data.get('balances', {})
    
    # Active positions to exclude from dust
    active_coins = [p['coin'].replace('_USDT', '') for p in data.get('state', {}).get('positions', [])]
    
    dust_value = 0.0
    dust_breakdown = []
    
    with open('history.json', 'r') as f:
        history = json.load(f)
        
    for coin, amount in balances.items():
        if coin == 'USDT' or coin in active_coins or amount <= 0:
            continue
            
        # Get price from history to estimate, or just fetch it
        symbol = f"{coin}_USDT"
        
        # We don't have get_ticker here easily without pionex_api, let's just use the last exit price from history if available
        last_price = 0
        for t in reversed(history):
            if t['coin'] == symbol:
                last_price = t['exit']
                break
        
        if last_price > 0:
            val = amount * last_price
            dust_value += val
            if val > 0.1:
                dust_breakdown.append((coin, amount, val))
        else:
            dust_breakdown.append((coin, amount, "Unknown Price"))
            
    print(f"Total estimated dust value: ${dust_value:.2f}")
    for c, a, v in sorted(dust_breakdown, key=lambda x: x[2] if isinstance(x[2], float) else 0, reverse=True):
        if isinstance(v, float):
            print(f"{c}: {a} = ${v:.2f}")
        else:
            print(f"{c}: {a} = {v}")

except Exception as e:
    print(e)
