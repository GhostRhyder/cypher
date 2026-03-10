import os
import hmac
import hashlib
import time
import requests
from dotenv import load_dotenv
from urllib.parse import urlencode

# --- Configuration ---
load_dotenv('/root/.openclaw/workspace/.env', override=True)
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

BASE_URL = "https://api.binance.com"

# --- Utility Functions ---
def send_binance_request(method: str, path: str, params: dict = None, body: dict = None):
    if params is None:
        params = {}
        
    # We never use body for GET/POST on Binance standard spot API (params go into query string)
    params['timestamp'] = int(time.time() * 1000)
    query_string = urlencode(params)
    
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    url = f"{BASE_URL}{path}?{query_string}&signature={signature}"
    
    headers = {
        "X-MBX-APIKEY": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers)
        else:
            raise ValueError("Unsupported HTTP method.")
            
        if response.status_code != 200:
             print(f"DEBUG: Status {response.status_code} | Body: {response.text}")

        response.raise_for_status()
        
        # Translate to Pionex format so cypher_swing.py doesn't need huge rewrites
        data = response.json()
        
        # Path specific translation
        if 'account' in path:
            # Translation for account balances
            return {
                "result": True,
                "data": {
                    "balances": [{"coin": a["asset"], "free": a["free"], "locked": a["locked"]} for a in data.get("balances", [])]
                }
            }
        elif 'ticker/price' in path or 'ticker/bookTicker' in path:
            return {"result": True, "data": data}
        elif 'order' in path:
            # POST order return
            return {"result": True, "data": data}
            
        return {"result": True, "data": data}

    except Exception as e:
        print(f"❌ API Request Failed: {e}")
        return {"result": False, "message": str(e)}

def get_candles(symbol: str, interval: str, limit: int = 100):
    """
    Fetches candlestick data (OHLCV) from Binance and maps it to Pionex format.
    Binance interval format: 1m, 5m, 15m, 30m, 1h, 4h, 8h, 12h, 1d, 1w
    Binance symbol format: BTCUSDT (no underscore)
    """
    binance_symbol = symbol.replace('_', '')
    
    # Binance klines uses public endpoint, no signature needed
    url = f"{BASE_URL}/api/v3/klines?symbol={binance_symbol}&interval={interval}&limit={limit}"
    
    try:
        res = requests.get(url)
        res.raise_for_status()
        klines = res.json()
        
        # Translate Binance klines to Pionex format
        # Binance: [Open time, Open, High, Low, Close, Volume, Close time, Quote asset volume, Number of trades, Taker buy base asset volume, Taker buy quote asset volume, Ignore]
        # Pionex expects list of dicts or list of lists: ['time', 'open', 'close', 'high', 'low', 'volume']
        # cypher_swing.py expects: df = pd.DataFrame(klines, columns=['time', 'open', 'close', 'high', 'low', 'volume'])
        
        formatted_klines = []
        for k in klines:
            formatted_klines.append([
                k[0],   # time
                k[1],   # open
                k[4],   # close
                k[2],   # high
                k[3],   # low
                k[5]    # volume
            ])
            
        return {"result": True, "data": {"klines": formatted_klines}}
    except Exception as e:
        print(f"❌ Candle Fetch Failed: {e}")
        return {"result": False, "data": None}

if __name__ == "__main__":
    print("Binance API Wrapper Loaded.")
