import requests

def execute():
    BASE_URL = "https://api.binance.com"
    info_url = f"{BASE_URL}/api/v3/exchangeInfo"
    info_res = requests.get(info_url).json()
    
    usdc_pairs = []
    for s in info_res['symbols']:
        if s['quoteAsset'] == 'USDC' and s['status'] == 'TRADING':
            usdc_pairs.append(s['symbol'])
            
    print(f"Total USDC quoted trading pairs: {len(usdc_pairs)}")
    print(f"Sample: {usdc_pairs[:10]}")

execute()
