import os, hmac, hashlib, time, requests
from dotenv import load_dotenv

load_dotenv('/root/.openclaw/workspace/.env', override=True)
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

timestamp = int(time.time() * 1000)
query_string = f"timestamp={timestamp}"
signature = hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
url = f"https://api.binance.com/api/v3/account?{query_string}&signature={signature}"
headers = {"X-MBX-APIKEY": API_KEY}

response = requests.get(url, headers=headers)
if response.status_code == 200:
    for a in response.json()['balances']:
        if float(a['free']) > 0 or float(a['locked']) > 0:
            print(f"{a['asset']}: Free: {a['free']} | Locked: {a['locked']}")
