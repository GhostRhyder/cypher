import os, hmac, hashlib, time, requests
from dotenv import load_dotenv
from urllib.parse import urlencode
import sys

load_dotenv('/root/.openclaw/workspace/.env', override=True)
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
BASE_URL = "https://api.binance.com"

def get_signature(query_string):
    return hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

def check_isolated_margin_balance(symbol):
    print(f"Checking Isolated Margin Account for {symbol}...")
    timestamp = int(time.time() * 1000)
    params = {"symbols": symbol, "timestamp": timestamp}
    qs = urlencode(params)
    url = f"{BASE_URL}/sapi/v1/margin/isolated/account?{qs}&signature={get_signature(qs)}"
    headers = {"X-MBX-APIKEY": API_KEY}
    
    res = requests.get(url, headers=headers)
    print("Status:", res.status_code)
    try:
        data = res.json()
        if "assets" in data:
            for asset in data["assets"]:
                if asset['symbol'] == symbol:
                    base_bal = float(asset['baseAsset']['free'])
                    base_locked = float(asset['baseAsset']['locked'])
                    quote_bal = float(asset['quoteAsset']['free'])
                    quote_locked = float(asset['quoteAsset']['locked'])
                    print(f"Isolated Pair: {asset['symbol']}")
                    print(f"  Base Asset ({asset['baseAsset']['asset']}): Free: {base_bal} | Locked: {base_locked}")
                    print(f"  Quote Asset ({asset['quoteAsset']['asset']}): Free: {quote_bal} | Locked: {quote_locked}")
                    return quote_bal # Return free USDC balance
            print(f"No isolated margin account found for {symbol}.")
        else:
            print("Response:", data)
    except Exception as e:
        print("Error parsing json:", e)
    return 0.0

if __name__ == "__main__":
    symbol_to_check = "BTCUSDC" # Default
    if len(sys.argv) > 1:
        symbol_to_check = sys.argv[1]
    usdc_balance = check_isolated_margin_balance(symbol_to_check)
    print(f"Free USDC in {symbol_to_check} Isolated Margin: {usdc_balance}")
