import os, hmac, hashlib, time, requests, math
from dotenv import load_dotenv
from urllib.parse import urlencode

load_dotenv('/root/.openclaw/workspace/.env', override=True)
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
BASE_URL = "https://api.binance.com"

def get_signature(query_string):
    return hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

def transfer_isolated_to_spot(symbol: str, asset: str, amount: float):
    print(f"Transferring {amount} {asset} from {symbol} Isolated Margin to Spot...")
    timestamp = int(time.time() * 1000)
    qs = urlencode({
        "asset": asset,
        "symbol": symbol,
        "transFrom": "ISOLATED_MARGIN",
        "transTo": "SPOT",
        "amount": amount,
        "timestamp": timestamp
    })
    url = f"{BASE_URL}/sapi/v1/margin/isolated/transfer?{qs}&signature={get_signature(qs)}"
    headers = {"X-MBX-APIKEY": API_KEY}
    
    res = requests.post(url, headers=headers)
    print("Transfer result:", res.status_code, res.text)
    return res.status_code == 200

if __name__ == "__main__":
    # First, get the current free USDC balance in SXTUSDC isolated margin
    # This part is duplicated from check_margin_balance.py, but for a self-contained script
    symbol = "SXTUSDC"
    asset_to_transfer = "USDC"
    
    timestamp = int(time.time() * 1000)
    params = {"symbols": symbol, "timestamp": timestamp}
    qs = urlencode(params)
    url = f"{BASE_URL}/sapi/v1/margin/isolated/account?{qs}&signature={get_signature(qs)}"
    headers = {"X-MBX-APIKEY": API_KEY}
    
    res = requests.get(url, headers=headers)
    margin_data = res.json()
    usdc_to_return = 0.0
    if "assets" in margin_data:
        for m in margin_data['assets']:
            if m['symbol'] == symbol:
                usdc_to_return = float(m['quoteAsset']['free'])
                break

    if usdc_to_return > 0:
        # Binance API expects amount with a certain precision, floor it to 2 decimal places for safety
        amount_to_transfer = math.floor(usdc_to_return * 100) / 100 # Transfer 5.0 USDC
        if transfer_isolated_to_spot(symbol, asset_to_transfer, amount_to_transfer):
            print("Transfer initiated successfully.")
        else:
            print("Transfer failed.")
    else:
        print(f"No {asset_to_transfer} found in {symbol} Isolated Margin account to transfer.")
