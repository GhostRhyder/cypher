import os, hmac, hashlib, time, requests, math
from dotenv import load_dotenv
from urllib.parse import urlencode

load_dotenv('/root/.openclaw/workspace/.env', override=True)
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
BASE_URL = "https://api.binance.com"

def get_signature(query_string):
    return hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

def execute():
    try:
        # 1. Enable Isolated Margin for BTCUSDC
        print("1. Enabling Isolated Margin for BTCUSDC...")
        ts = int(time.time() * 1000)
        qs = urlencode({"symbol": "BTCUSDC", "timestamp": ts})
        url = f"{BASE_URL}/sapi/v1/margin/isolated/account?{qs}&signature={get_signature(qs)}"
        res = requests.post(url, headers={"X-MBX-APIKEY": API_KEY})
        # If already enabled, ignore error
        print("Enable result:", res.status_code, res.text)
        
        # 2. Transfer 5 USDC from SPOT to ISOLATED MARGIN
        print("2. Transferring 5 USDC to ISOLATED MARGIN...")
        ts = int(time.time() * 1000)
        qs = urlencode({"asset": "USDC", "symbol": "BTCUSDC", "transFrom": "SPOT", "transTo": "ISOLATED_MARGIN", "amount": 5.0, "timestamp": ts})
        url = f"{BASE_URL}/sapi/v1/margin/isolated/transfer?{qs}&signature={get_signature(qs)}"
        res = requests.post(url, headers={"X-MBX-APIKEY": API_KEY})
        print("Transfer result:", res.status_code, res.text)
        
        # Wait a sec for transfer to clear
        time.sleep(2)
        
        # 3. Borrow 5 USDC (Leverage the collateral)
        print("3. Borrowing 5 USDC in ISOLATED MARGIN...")
        ts = int(time.time() * 1000)
        qs = urlencode({"asset": "USDC", "isIsolated": "TRUE", "symbol": "BTCUSDC", "amount": 5.0, "timestamp": ts})
        url = f"{BASE_URL}/sapi/v1/margin/loan?{qs}&signature={get_signature(qs)}"
        res = requests.post(url, headers={"X-MBX-APIKEY": API_KEY})
        print("Borrow result:", res.status_code, res.text)
        
        # Wait a sec
        time.sleep(2)
        
        # 4. Check available USDC in margin wallet
        print("4. Checking Margin Balance...")
        ts = int(time.time() * 1000)
        qs = urlencode({"symbols": "BTCUSDC", "timestamp": ts})
        url = f"{BASE_URL}/sapi/v1/margin/isolated/account?{qs}&signature={get_signature(qs)}"
        res = requests.get(url, headers={"X-MBX-APIKEY": API_KEY})
        margin_data = res.json()
        margin_usdc = 0.0
        for m in margin_data.get('assets', []):
            if m['symbol'] == 'BTCUSDC':
                margin_usdc = float(m['quoteAsset']['free'])
        print(f"Margin USDC available: {margin_usdc}")
        
        # If we failed to transfer/borrow, try to clean up
        if margin_usdc < 9.0:
            print("Failed to secure 10 USDC (5 collateral + 5 borrowed). Aborting trade.")
            return

        # 5. Place Market BUY on BTCUSDC using 10 USDC (Total 2x lev)
        print("5. Market BUY BTC using 10 USDC...")
        ts = int(time.time() * 1000)
        qs = urlencode({"symbol": "BTCUSDC", "isIsolated": "TRUE", "side": "BUY", "type": "MARKET", "quoteOrderQty": 9.9, "timestamp": ts})
        url = f"{BASE_URL}/sapi/v1/margin/order?{qs}&signature={get_signature(qs)}"
        res = requests.post(url, headers={"X-MBX-APIKEY": API_KEY})
        print("Buy result:", res.status_code, res.text)
        
        # Wait a sec
        time.sleep(3)

        # 6. Check available BTC in margin wallet to sell
        print("6. Checking BTC Balance in Margin...")
        ts = int(time.time() * 1000)
        qs = urlencode({"symbols": "BTCUSDC", "timestamp": ts})
        url = f"{BASE_URL}/sapi/v1/margin/isolated/account?{qs}&signature={get_signature(qs)}"
        res = requests.get(url, headers={"X-MBX-APIKEY": API_KEY})
        margin_data = res.json()
        margin_btc = 0.0
        for m in margin_data.get('assets', []):
            if m['symbol'] == 'BTCUSDC':
                margin_btc = float(m['baseAsset']['free'])
        print(f"Margin BTC available: {margin_btc}")
        
        if margin_btc > 0:
            # 7. Place Market SELL on BTCUSDC using full BTC amount
            print("7. Market SELL BTC...")
            btc_str = f"{math.floor(margin_btc * 100000) / 100000:.5f}" # format for step size safety
            ts = int(time.time() * 1000)
            qs = urlencode({"symbol": "BTCUSDC", "isIsolated": "TRUE", "side": "SELL", "type": "MARKET", "quantity": btc_str, "timestamp": ts})
            url = f"{BASE_URL}/sapi/v1/margin/order?{qs}&signature={get_signature(qs)}"
            res = requests.post(url, headers={"X-MBX-APIKEY": API_KEY})
            print("Sell result:", res.status_code, res.text)
        
        time.sleep(3)
        
        # 8. Repay 5 USDC
        print("8. Repaying borrowed 5 USDC + Interest...")
        ts = int(time.time() * 1000)
        qs = urlencode({"asset": "USDC", "isIsolated": "TRUE", "symbol": "BTCUSDC", "amount": 5.01, "timestamp": ts})
        url = f"{BASE_URL}/sapi/v1/margin/repay?{qs}&signature={get_signature(qs)}"
        res = requests.post(url, headers={"X-MBX-APIKEY": API_KEY})
        print("Repay result:", res.status_code, res.text)
        
        time.sleep(2)
        
        # 9. Transfer Remaining USDC back to SPOT
        print("9. Transferring remaining USDC to SPOT...")
        ts = int(time.time() * 1000)
        qs = urlencode({"symbols": "BTCUSDC", "timestamp": ts})
        url = f"{BASE_URL}/sapi/v1/margin/isolated/account?{qs}&signature={get_signature(qs)}"
        res = requests.get(url, headers={"X-MBX-APIKEY": API_KEY})
        margin_data = res.json()
        usdc_to_return = 0.0
        for m in margin_data.get('assets', []):
            if m['symbol'] == 'BTCUSDC':
                usdc_to_return = float(m['quoteAsset']['free'])
        
        if usdc_to_return > 0:
            ts = int(time.time() * 1000)
            qs = urlencode({"asset": "USDC", "symbol": "BTCUSDC", "transFrom": "ISOLATED_MARGIN", "transTo": "SPOT", "amount": math.floor(usdc_to_return*100)/100, "timestamp": ts})
            url = f"{BASE_URL}/sapi/v1/margin/isolated/transfer?{qs}&signature={get_signature(qs)}"
            res = requests.post(url, headers={"X-MBX-APIKEY": API_KEY})
            print("Transfer back result:", res.status_code, res.text)

    except Exception as e:
        print("Error during test sequence:", e)

execute()
