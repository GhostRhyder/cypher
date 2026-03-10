import os, hmac, hashlib, time, requests, math
from dotenv import load_dotenv

load_dotenv('/root/.openclaw/workspace/.env', override=True)
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

BASE_URL = "https://api.binance.com"

def get_signature(query_string):
    return hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

def execute():
    # 1. Get USDC balance
    timestamp = int(time.time() * 1000)
    qs = f"timestamp={timestamp}"
    url = f"{BASE_URL}/api/v3/account?{qs}&signature={get_signature(qs)}"
    headers = {"X-MBX-APIKEY": API_KEY}
    res = requests.get(url, headers=headers).json()
    usdc_bal = 0.0
    for a in res.get('balances', []):
        if a['asset'] == 'USDC':
            usdc_bal = float(a['free'])
            break
            
    if usdc_bal < 1.0:
        print("Not enough USDC to convert.")
        return

    # 2. Get exchange info for USDCUSDT
    info_url = f"{BASE_URL}/api/v3/exchangeInfo?symbol=USDCUSDT"
    info_res = requests.get(info_url).json()
    step_size = "1.00000000"
    for filt in info_res['symbols'][0]['filters']:
        if filt['filterType'] == 'LOT_SIZE':
            step_size = filt['stepSize']
            break
    
    # Calculate precision based on step size
    precision = 0
    if '.' in step_size:
        precision = len(step_size.rstrip('0').split('.')[1])
        
    qty = math.floor(usdc_bal * (10 ** precision)) / (10 ** precision)
    qty_str = f"{qty:.{precision}f}"
    
    print(f"Executing MARKET SELL of {qty_str} USDC for USDT")
    
    # 3. Place order
    timestamp = int(time.time() * 1000)
    qs = f"symbol=USDCUSDT&side=SELL&type=MARKET&quantity={qty_str}&timestamp={timestamp}"
    url = f"{BASE_URL}/api/v3/order?{qs}&signature={get_signature(qs)}"
    
    order_res = requests.post(url, headers=headers)
    print(order_res.status_code, order_res.text)

execute()
