import urllib.request
import json

url = "https://api.binance.com/api/v3/klines?symbol=JASMYUSDT&interval=1d&limit=30"
try:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        closes = [float(candle[4]) for candle in data]
        highs = [float(candle[2]) for candle in data]
        current_price = closes[-1]
        max_high = max(highs)
        print(f"Daily Current: {current_price:.6f}, 30d High: {max_high:.6f}")
except Exception as e:
    print(f"Error: {e}")
