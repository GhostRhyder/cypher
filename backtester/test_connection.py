import requests
import json

def test_binance():
    print("Testing connection to Binance API...")
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print("✅ Successfully connected to Binance API!")
            data = response.json()
            usdt_pairs = [item['symbol'] for item in data if item['symbol'].endswith('USDT')]
            print(f"Found {len(usdt_pairs)} USDT pairs.")
            print(f"Top 5 by volume: {[item['symbol'] for item in sorted(data, key=lambda x: float(x['quoteVolume']), reverse=True)[:5]]}")
        else:
            print(f"❌ Failed to connect. Status code: {response.status_code}")
    except Exception as e:
        print(f"❌ Error connecting to Binance: {e}")

if __name__ == "__main__":
    test_binance()
