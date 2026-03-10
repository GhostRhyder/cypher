import requests

try:
    data = requests.get('http://127.0.0.1:8080/api/data').json()
    total_equity = data['balances'].get('USDT', 0.0)
    print(f"Free USDT: {total_equity}")
    
    # Active positions
    active = data.get('state', {}).get('positions', [])
    for pos in active:
        val = pos.get('amount_usdt', 0.0)
        total_equity += val
        print(f"Active {pos['coin']}: ${val:.2f}")
        
    print(f"Total Equity (Free USDT + Active Positions): ${total_equity:.2f}")

except Exception as e:
    print(e)
