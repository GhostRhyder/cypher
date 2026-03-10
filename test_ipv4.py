import socket
import requests.packages.urllib3.util.connection as urllib3_cn

def allowed_gai_family():
    return socket.AF_INET

urllib3_cn.allowed_gai_family = allowed_gai_family

import os
import hmac
import hashlib
import time
import requests
from dotenv import load_dotenv

load_dotenv('/root/.openclaw/workspace/.env')
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

BASE_URL = "https://api.binance.com"

def get_binance_balance():
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    url = f"{BASE_URL}/api/v3/account?{query_string}&signature={signature}"
    headers = {
        "X-MBX-APIKEY": API_KEY
    }
    response = requests.get(url, headers=headers)
    print(response.status_code)
    print(response.json().keys())

get_binance_balance()
