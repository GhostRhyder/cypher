import time
import json
from datetime import datetime
from pionex_api_template import send_pionex_request

LOG_FILE = "trade_daemon.log"

def log(msg):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def get_precision(symbol):
    try:
        res = send_pionex_request("GET", "/api/v1/common/symbols")
        for s in res['data']['symbols']:
            if s['symbol'] == symbol:
                return int(s.get('basePrecision', 4))
    except:
        pass
    return 4

def truncate(n, decimals=0):
    multiplier = 10 ** decimals
    return int(n * multiplier) / multiplier

def get_balances():
    try:
        res = send_pionex_request("GET", "/api/v1/account/balances")
        bals = {}
        for item in res['data']['balances']:
            free = float(item['free'])
            if free > 0:
                bals[item['coin']] = free
        return bals
    except Exception as e:
        log(f"Balance error: {e}")
        return {}

def get_tickers():
    try:
        res = send_pionex_request("GET", "/api/v1/market/tickers")
        return {t['symbol']: float(t['close']) for t in res['data']['tickers']}
    except:
        return {}

def market_sell(symbol, qty):
    prec = get_precision(symbol)
    qty_trunc = truncate(qty, prec)
    if qty_trunc <= 0: return False
    body = {"symbol": symbol, "side": "SELL", "type": "MARKET", "size": str(qty_trunc)}
    try:
        res = send_pionex_request("POST", "/api/v1/trade/order", body)
        log(f"SELL {symbol} {qty_trunc} -> {res.get('result', res)}")
        return res.get('result') == True
    except Exception as e:
        log(f"Sell error: {e}")
        return False

def run_daemon():
    log("🚀 Daemon started. Monitoring TRX, SOL, ADA...")
    
    # Initialize entry prices based on current market (baseline)
    tickers = get_tickers()
    positions = {}
    for coin in ["TRX", "SOL", "ADA"]:
        sym = f"{coin}_USDT"
        if sym in tickers:
            positions[coin] = tickers[sym]
            log(f"Tracking {coin} at baseline entry approx {tickers[sym]}")

    log("V1 Daemon rules: TP at +1.5%, SL at -1.0%. Polling every 60s.")

    while True:
        try:
            time.sleep(60)
            bals = get_balances()
            tickers = get_tickers()
            
            for coin in list(positions.keys()):
                sym = f"{coin}_USDT"
                # If balance is less than ~$2 worth, it's just dust or already sold
                if coin not in bals or bals[coin] * tickers.get(sym, 0) < 2.0:
                    positions.pop(coin)
                    log(f"{coin} position closed or dust. Stopped tracking.")
                    continue
                    
                current_price = tickers.get(sym)
                entry = positions[coin]
                if not current_price: continue
                
                pct_change = (current_price - entry) / entry
                
                if pct_change >= 0.015:
                    log(f"🟢 TAKE PROFIT TRIGGERED for {coin}: +{pct_change*100:.2f}%")
                    market_sell(sym, bals[coin])
                elif pct_change <= -0.010:
                    log(f"🔴 STOP LOSS TRIGGERED for {coin}: {pct_change*100:.2f}%")
                    market_sell(sym, bals[coin])
                    
            if not positions:
                log("All monitored positions closed safely to USDT. Daemon entering standby.")
                break # Exit loop once all 3 positions are secured for the weekend
                
        except Exception as e:
            log(f"Daemon error loop: {e}")
            time.sleep(60)

if __name__ == '__main__':
    run_daemon()