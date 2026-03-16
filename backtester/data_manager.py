import pandas as pd
import requests
import time
from datetime import datetime

class DataManager:
    BASE_URL = "https://api.binance.com/api/v3"
    
    # Hardcoded fallback list in case Binance API is unreachable
    FALLBACK_COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "AVAXUSDT", "DOGEUSDT", "DOTUSDT", "LINKUSDT"]

    def get_top_volume_coins(self, limit=10):
        """Fetch top 10 coins by 24h volume from Binance with fallback."""
        try:
            url = f"{self.BASE_URL}/ticker/24hr"
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                print(f"Binance API returned status {response.status_code}")
                return self.FALLBACK_COINS
                
            data = response.json()
            # Filter for USDT pairs and sort by quoteVolume
            usdt_pairs = [item for item in data if item['symbol'].endswith('USDT') and 'UP' not in item['symbol'] and 'DOWN' not in item['symbol']]
            sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x['quoteVolume']), reverse=True)
            return [item['symbol'] for item in sorted_pairs[:limit]]
        except Exception as e:
            print(f"Error fetching top coins: {e}")
            return self.FALLBACK_COINS

    def fetch_candles(self, symbol, interval="5m", limit=500):
        """Fetch historical klines from Binance with reduced limit for faster backtests."""
        try:
            symbol = symbol.replace("_", "")
            url = f"{self.BASE_URL}/klines"
            params = {
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }
            response = requests.get(url, params=params, timeout=15)
            if response.status_code != 200:
                print(f"Binance API returned status {response.status_code} for {symbol}")
                return None
                
            data = response.json()
            if not isinstance(data, list):
                print(f"Unexpected data format from Binance: {data}")
                return None
                
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Convert to numeric
            cols = ['open', 'high', 'low', 'close', 'volume']
            df[cols] = df[cols].apply(pd.to_numeric)
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"Error fetching candles for {symbol}: {e}")
            return None
