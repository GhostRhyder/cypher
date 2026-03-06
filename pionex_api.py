import hmac
import hashlib
import json
import time
import requests
from urllib.parse import urlencode

class PionexClient:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.pionex.com"

    def _sign(self, method, path, params=None):
        timestamp = str(int(time.time() * 1000))
        # Sort params alphabetically for signature if needed (Pionex sometimes requires it)
        # But for simple GET requests without query params in URL, it's usually straightforward.
        # Let's try standard approach first.
        
        query_string = urlencode(sorted(params.items())) if params else ""
        body_string = "" # For POST requests, body is JSON string
        
        pre_hash = f"{timestamp}{method}{path}{query_string}{body_string}"
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            pre_hash.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return timestamp, signature

    def request(self, method, endpoint, params=None):
        if params is None:
            params = {}
        
        timestamp = str(int(time.time() * 1000))
        params['timestamp'] = timestamp
        
        # Sort params for signature
        query_string = urlencode(sorted(params.items()))
        body_string = "" # GET request usually has no body
        
        pre_hash = f"{method}{endpoint}?{query_string}{body_string}"
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            pre_hash.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            "PIONEX-KEY": self.api_key,
            "PIONEX-SIGNATURE": signature,
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}{endpoint}?{query_string}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            else:
                response = requests.post(url, headers=headers, json=params)
            
            # DEBUG: Print raw response if error
            if response.status_code != 200:
                print(f"DEBUG: Status {response.status_code} | Body: {response.text}")
                
            return response.json()
        except Exception as e:
            print(f"❌ Request Failed: {e}")
            return None

    def get_balance(self):
        return self.request("GET", "/api/v1/account/balances")

    def get_tickers(self):
        return self.request("GET", "/api/v1/market/tickers")
