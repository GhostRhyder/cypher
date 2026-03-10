import urllib.request
import json
import numpy as np

def get_klines(symbol="JASMYUSDT", interval="1h", limit=50):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())

def calculate_rsi(prices, n=14):
    deltas = np.diff(prices)
    seed = deltas[:n+1]
    up = seed[seed>=0].sum()/n
    down = -seed[seed<0].sum()/n
    rs = up/down if down != 0 else 0
    rsi = np.zeros_like(prices)
    rsi[:n] = 100. - 100./(1.+rs)
    for i in range(n, len(prices)):
        delta = deltas[i-1]
        if delta > 0:
            upval = delta
            downval = 0.
        else:
            upval = 0.
            downval = -delta
        up = (up*(n-1) + upval)/n
        down = (down*(n-1) + downval)/n
        rs = up/down if down != 0 else 0
        rsi[i] = 100. - 100./(1.+rs)
    return rsi[-1]

data = get_klines()
closes = np.array([float(x[4]) for x in data])
highs = np.array([float(x[2]) for x in data])
lows = np.array([float(x[3]) for x in data])
volumes = np.array([float(x[5]) for x in data])

current_price = closes[-1]
rsi_14 = calculate_rsi(closes)
sma_20 = np.mean(closes[-20:])
sma_50 = np.mean(closes[-50:])

print(f"Current Price: {current_price}")
print(f"RSI (14): {rsi_14:.2f}")
print(f"SMA (20): {sma_20:.6f}")
print(f"SMA (50): {sma_50:.6f}")
print(f"Recent High: {max(highs[-10:])}")
print(f"Recent Low: {min(lows[-10:])}")

