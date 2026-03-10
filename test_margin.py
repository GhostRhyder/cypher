import os, hmac, hashlib, time, requests
from dotenv import load_dotenv
from urllib.parse import urlencode

load_dotenv('/root/.openclaw/workspace/.env', override=True)
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
BASE_URL = "https://api.binance.com"

def get_signature(query_string):
    return hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

def check_margin_account():
    print("Checking Isolated Margin Account...")
    timestamp = int(time.time() * 1000)
    params = {"timestamp": timestamp}
    qs = urlencode(params)
    url = f"{BASE_URL}/sapi/v1/margin/isolated/account?{qs}&signature={get_signature(qs)}"
    headers = {"X-MBX-APIKEY": API_KEY}
    
    res = requests.get(url, headers=headers)
    print("Status:", res.status_code)
    try:
        data = res.json()
        print("Keys:", data.keys())
        if "assets" in data:
            for asset in data["assets"]:
                # Only print assets that have some balance
                base_bal = float(asset['baseAsset']['totalAsset'])
                quote_bal = float(asset['quoteAsset']['totalAsset'])
                if base_bal > 0 or quote_bal > 0:
                    print(f"Isolated Pair: {asset['symbol']} | Base: {base_bal} | Quote: {quote_bal}")
            print(f"Total Isolated Margin Assets listed: {len(data['assets'])}")
        else:
            print("Response:", data)
    except Exception as e:
        print("Error parsing json:", e)

check_margin_account()
