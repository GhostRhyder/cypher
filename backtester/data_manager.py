import pandas as pd
import requests
import time
from datetime import datetime

class DataManager:
    BASE_URL = "https://api.binance.com/api/v3"
    
    # Hardcoded list to match Cypher's allowed universe + candidates
    CYPHER_UNIVERSE = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "TRXUSDT", 
        "XRPUSDT", "LINKUSDT", "AVAXUSDT", "DOGEUSDT", "BNBUSDT", 
        "PEPEUSDT", "SUIUSDT", "OPNUSDT", "TAOUSDT", "TRUMPUSDT", 
        "NEARUSDT", "FETUSDT", "ZECUSDT"
    ]

    def get_top_volume_coins(self, limit=10):
        """Returns the specific coins Ghost needs to optimize for the daemon."""
        return self.CYPHER_UNIVERSE

    def fetch_candles(self, symbol, interval="5m", limit=2000):
        """Fetch historical klines from Binance. Increased limit to 2000 for ~7 days of 5m data."""
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
