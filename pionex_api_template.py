import os
import hmac
import hashlib
import time
import json
import requests
from dotenv import load_dotenv
from urllib.parse import urlencode

# --- Configuration ---
load_dotenv()
API_KEY = os.getenv("PIONEX_API_KEY")
API_SECRET = os.getenv("PIONEX_API_SECRET")

# Base URL for Pionex API
BASE_URL = "https://api.pionex.com" 

# --- Utility Functions ---
def generate_pionex_signature(secret: str, method: str, path: str, params: dict = None, body: dict = None) -> str:
    """
    Generates the Pionex API signature.
    Logic: Method + Path + ? + QueryString (sorted) + Body
    """
    # Construct the message to sign
    message = method.upper() + path

    # For both GET and POST, add query string if params exist (timestamp is in params)
    if params:
        query_string = urlencode(sorted(params.items()))
        message += "?" + query_string

    if method.upper() == "POST" and body:
        # For POST, append JSON body
        message += json.dumps(body, separators=(',', ':'))

    # Generate HMAC-SHA256 signature
    signature = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # DEBUG: Print message being signed
    print(f"DEBUG SIGN: {message}")

    return signature

def send_pionex_request(method: str, path: str, params: dict = None, body: dict = None):
    """
    Sends an authenticated request to the Pionex API.
    """
    nonce = str(int(time.time() * 1000))
    
    if method.upper() == "GET":
        if params is None:
            params = {}
        # Important: Add timestamp to params BEFORE signing
        params['timestamp'] = nonce
    elif method.upper() == "POST":
         # For POST, timestamp needs to be in QUERY STRING (url params), NOT body
         if params is None:
             params = {}
         params['timestamp'] = nonce

    # Generate Signature using the updated params
    signature = generate_pionex_signature(API_SECRET, method, path, params, body)

    headers = {
        "PIONEX-KEY": API_KEY,
        "PIONEX-TIMESTAMP": nonce,
        "PIONEX-SIGNATURE": signature,
        "Content-Type": "application/json"
    }

    # Construct URL with query string MANUALLY to match signature exactly
    query_string = urlencode(sorted(params.items()))
    url = f"{BASE_URL}{path}?{query_string}"

    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers) # No params arg needed
        elif method.upper() == "POST":
            # Manually serialize JSON to match signature
            json_body = json.dumps(body, separators=(',', ':'))
            response = requests.post(url, headers=headers, data=json_body)
        else:
            raise ValueError("Unsupported HTTP method.")

        # DEBUG: Print raw response if error
        if response.status_code != 200:
             print(f"DEBUG: Status {response.status_code} | Body: {response.text}")

        response.raise_for_status() 
        return response.json()

    except Exception as e:
        print(f"❌ API Request Failed: {e}")
        return None

def get_candles(symbol: str, interval: str, limit: int = 100):
    """
    Fetches candlestick data (OHLCV).
    Intervals: 1m, 5m, 15m, 30m, 1h, 4h, 8h, 12h, 1d, 1w
    """
    # Endpoint: /api/v1/market/klines
    # Params: symbol, interval, limit
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    return send_pionex_request("GET", "/api/v1/market/klines", params=params)

def place_market_buy(symbol: str, quote_amount: float):
    """
    Places a MARKET BUY order for a specific amount of Quote Currency (e.g., 10 USDT).
    """
    # Endpoint: /api/v1/trade/order
    # Body: { symbol, side='BUY', type='MARKET', amount=quote_amount }
    # Note: Pionex uses 'amount' for quote quantity in MARKET BUY? Or 'quantity'?
    # Checking docs... usually 'amount' is quote qty for market buy.
    
    body = {
        "symbol": symbol,
        "side": "BUY",
        "type": "MARKET",
        "amount": str(quote_amount) # Quote currency amount (USDT)
    }
    return send_pionex_request("POST", "/api/v1/trade/order", body=body)

if __name__ == "__main__":
    print("Pionex API Template Loaded.")
