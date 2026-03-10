import socket
orig_getaddrinfo = socket.getaddrinfo

def getaddrinfo_v4(*args, **kwargs):
    res = orig_getaddrinfo(*args, **kwargs)
    return [r for r in res if r[0] == socket.AF_INET]

socket.getaddrinfo = getaddrinfo_v4

import os, hmac, hashlib, time, requests
from dotenv import load_dotenv

load_dotenv('/root/.openclaw/workspace/.env')
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

BASE_URL = "https://api.binance.com"

timestamp = int(time.time() * 1000)
query_string = f"timestamp={timestamp}"
signature = hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
url = f"{BASE_URL}/api/v3/account?{query_string}&signature={signature}"
headers = {"X-MBX-APIKEY": API_KEY}

response = requests.get(url, headers=headers)
print(response.status_code)
if response.status_code == 200:
    for a in response.json()['balances']:
        if float(a['free']) > 0: print(a)
