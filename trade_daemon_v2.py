import time
import json
import pandas as pd
import numpy as np
import talib
from datetime import datetime
from pionex_api_template import send_pionex_request, get_candles

LOG_FILE = "trade_daemon_v2.log"
STATE_FILE = "state.json"
HISTORY_FILE = "history.json"

# FSM States
HUNTING = "HUNTING"
DEPLOYED = "DEPLOYED"
COMPOUNDING = "COMPOUNDING"
COOLDOWN = "COOLDOWN"

# Config (Adjusted per Ghost's parameters)
MAX_POSITIONS = 3          # Allow up to 3 concurrent trades
MIN_TRADE_SIZE = 15.0      # Safety margin above dust limits
HARD_STOP_PCT = 0.015      # -1.5% absolute floor (defense)
TRAIL_ACTIVATION = 0.01    # Must reach +1.0% profit to activate trailing stop
TRAIL_DISTANCE = 0.01      # Trailing stop stays 1.0% behind the peak
COOLDOWN_MINUTES = 5       # Wait time after a stop-out

def log(msg):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[V2] [{stamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def save_state(state, active_positions=[], pnl=0.0):
    # active_positions is a list of dicts:
    # [{'coin': 'PEPE_USDT', 'entry': ..., 'current': ..., 'peak': ..., 'pnl': ...}]
    data = {
        "state": state,
        "positions": active_positions,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)
    except:
        pass

def save_trade_history(coin, entry, exit_price, pnl_pct):
    trade = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "coin": coin,
        "entry": entry,
        "exit": exit_price,
        "pnl_pct": pnl_pct,
        "result": "WIN" if pnl_pct >= 0 else "LOSS"
    }
    
    history = []
    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
    except:
        history = []
        
    history.append(trade)
    # Keep last 50
    if len(history) > 50:
        history = history[-50:]
        
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except:
        pass

def get_usdt_balance():
    try:
        res = send_pionex_request("GET", "/api/v1/account/balances")
        for item in res['data']['balances']:
            if item['coin'] == 'USDT':
                return float(item['free'])
        return 0.0
    except:
        return 0.0

def get_ticker(symbol):
    try:
        # Fix: Pass symbol as params, not in path
        res = send_pionex_request("GET", "/api/v1/market/tickers", params={"symbol": symbol})
        return float(res['data']['tickers'][0]['close'])
    except:
        return None

def get_top_volume_coins(limit=10):
    try:
        res = send_pionex_request("GET", "/api/v1/market/tickers")
        tickers = res['data']['tickers']
        usdt_pairs = [t for t in tickers if t['symbol'].endswith('_USDT') and 'BEAR' not in t['symbol'] and 'BULL' not in t['symbol']]
        sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x['volume']), reverse=True)
        return [t['symbol'] for t in sorted_pairs[:limit]]
    except Exception as e:
        log(f"Error fetching top coins: {e}")
        return []

def scan_market():
    """Scans top 10 coins on 5M for S5_Scalp or S4_Momentum. Returns best symbol or None."""
    top_coins = get_top_volume_coins(10)
    for symbol in top_coins:
        resp = get_candles(symbol, "5M", limit=100)
        if not resp or 'data' not in resp or 'klines' not in resp['data']:
            continue
        
        klines = resp['data']['klines']
        if not klines or len(klines) < 50:
            continue
            
        df = pd.DataFrame(klines, columns=['time', 'open', 'close', 'high', 'low', 'volume'])
        df['close'] = pd.to_numeric(df['close']).astype(float)
        close = df['close'].values
        
        # S5_Scalp: StochRSI < 20 and Cross Up
        try:
            fastk, fastd = talib.STOCHRSI(close, timeperiod=14, fastk_period=3, fastd_period=3, fastd_matype=0)
            if fastk[-1] < 20 and fastk[-1] > fastd[-1] and fastk[-2] <= fastd[-2]:
                log(f"[SCANNER] 🔥 S5_Scalp detected on {symbol}")
                return symbol
        except:
            pass

        # S4_Momentum: MACD > Signal + RSI > 50
        try:
            macd, macd_signal, _ = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
            rsi = talib.RSI(close, timeperiod=14)
            if macd[-1] > macd_signal[-1] and rsi[-1] > 50 and macd[-2] <= macd_signal[-2]: # Fresh cross
                log(f"[SCANNER] 🔥 S4_Momentum detected on {symbol}")
                return symbol
        except:
            pass
            
    return None

def execute_buy(symbol, usdt_amount):
    # Retrieve precision and place market buy
    try:
        # Force 2 decimals for USDT pairs to prevent precision errors
        amt_str = f"{usdt_amount:.2f}"
        
        body = {"symbol": symbol, "side": "BUY", "type": "MARKET", "amount": amt_str}
        log(f"[DEBUG] Placing BUY Order: {body}")
        resp = send_pionex_request("POST", "/api/v1/trade/order", body=body)
        if resp.get('result'):
            log(f"[EXECUTE] ✅ BUY {symbol} for ${amt_str} USDT")
            return True
        else:
            log(f"[EXECUTE] ❌ BUY FAILED: {resp}")
            return False
    except Exception as e:
        log(f"[EXECUTE] Error buying {symbol}: {e}")
        return False

def execute_sell(symbol):
    # Retrieve base balance and place market sell
    try:
        coin = symbol.split('_')[0]
        res = send_pionex_request("GET", "/api/v1/account/balances")
        balance = 0.0
        for b in res['data']['balances']:
            if b['coin'] == coin:
                balance = float(b['free'])
                break
                
        if balance <= 0:
            return False
            
        sym_res = send_pionex_request("GET", "/api/v1/common/symbols")
        base_prec = 4
        for s in sym_res['data']['symbols']:
            if s['symbol'] == symbol:
                base_prec = int(s.get('basePrecision', 4))
                break
                
        if base_prec == 0:
            size_str = str(int(balance))
        else:
            multiplier = 10 ** base_prec
            size_str = str(int(balance * multiplier) / multiplier)
        
        body = {"symbol": symbol, "side": "SELL", "type": "MARKET", "size": size_str}
        resp = send_pionex_request("POST", "/api/v1/trade/order", body=body)
        if resp.get('result'):
            log(f"[EXECUTE] ✅ SELL {symbol} size {size_str}")
            return True
        return False
    except Exception as e:
        log(f"[EXECUTE] Error selling {symbol}: {e}")
        return False

def run_v2_daemon():
    state = HUNTING
    active_coin = None
    entry_price = 0.0
    highest_price = 0.0
    trade_size = MIN_TRADE_SIZE
    
    log(f"Initialize V2 Auto-Compounder FSM. Min Size: ${MIN_TRADE_SIZE}")

    # Startup Check: Do we already have a bag?
    try:
        res = send_pionex_request("GET", "/api/v1/account/balances")
        for item in res['data']['balances']:
            coin = item['coin']
            free = float(item['free'])
            if coin != 'USDT' and free > 0:
                # Check value in USDT roughly
                symbol = f"{coin}_USDT"
                price = get_ticker(symbol)
                if price:
                    value = free * price
                    if value > 10.0: # Assume active trade if > $10
                        log(f"[RESUME] Found existing bag of {symbol} (${value:.2f}). Resuming management.")
                        active_coin = symbol
                        entry_price = price # Reset baseline to now
                        highest_price = price
                        state = DEPLOYED
                        break
    except Exception as e:
        log(f"Startup check failed: {e}")

    while True:
        try:
            if state == HUNTING:
                usdt = get_usdt_balance()
                if usdt < MIN_TRADE_SIZE:
                    log(f"Insufficient USDT (${usdt:.2f}). Waiting for manual intervention or V1 to close.")
                    time.sleep(300)
                    continue
                
                # Cap trade size at $15 or available balance, whichever is lower
                trade_size = min(usdt * 0.98, 15.0) 
                
                log(f"[HUNTING] Scanning 5M charts for target. Arsenal: ${trade_size:.2f}")
                save_state(HUNTING, pnl=0.0)
                
                target_symbol = scan_market()
                
                if target_symbol:
                    if execute_buy(target_symbol, trade_size):
                        active_coin = target_symbol
                        time.sleep(2) # Give exchange a moment to process fill
                        entry_price = get_ticker(target_symbol)
                        highest_price = entry_price
                        state = DEPLOYED
                        log(f"[TRANSITION] -> DEPLOYED on {active_coin} at Entry: {entry_price}")
                        save_state(DEPLOYED, active_coin, entry_price, entry_price, highest_price, 0.0)
                        continue
                
                time.sleep(180) # 3 minutes between scans

            elif state == DEPLOYED:
                current_price = get_ticker(active_coin)
                if not current_price:
                    time.sleep(10)
                    continue
                
                if current_price > highest_price:
                    highest_price = current_price
                    
                profit_pct = (current_price - entry_price) / entry_price
                peak_pct = (highest_price - entry_price) / entry_price
                drop_from_peak = (highest_price - current_price) / highest_price
                
                # Defense: Hard Stop Loss
                if profit_pct <= -HARD_STOP_PCT:
                    log(f"[DEPLOYED] 🔴 HARD STOP HIT on {active_coin} at {profit_pct*100:.2f}%. Liquidating.")
                    save_trade_history(active_coin, entry_price, current_price, profit_pct * 100)
                    execute_sell(active_coin)
                    state = COOLDOWN
                    continue
                
                # Offense: Trailing Stop Logic (No Ceiling)
                if peak_pct >= TRAIL_ACTIVATION:
                    if drop_from_peak >= TRAIL_DISTANCE:
                        log(f"[DEPLOYED] 🟢 TRAILING STOP HIT on {active_coin}. Secured profit from peak! Liquidating.")
                        save_trade_history(active_coin, entry_price, current_price, profit_pct * 100)
                        execute_sell(active_coin)
                        state = COMPOUNDING
                        continue
                
                log(f"[{active_coin}] PnL: {profit_pct*100:.2f}% | Peak: {peak_pct*100:.2f}%")
                save_state(DEPLOYED, active_coin, entry_price, current_price, highest_price, profit_pct * 100)
                time.sleep(30) # High frequency monitoring while deployed

            elif state == COMPOUNDING:
                log("[COMPOUNDING] Trade successful. Re-calculating wallet balances...")
                save_state(COMPOUNDING, pnl=0.0)
                time.sleep(10) 
                state = HUNTING
                log("[TRANSITION] -> HUNTING (Compounded)")

            elif state == COOLDOWN:
                log(f"[COOLDOWN] Taking a {COOLDOWN_MINUTES}-minute breather to avoid revenge trading.")
                save_state(COOLDOWN, pnl=0.0)
                time.sleep(COOLDOWN_MINUTES * 60)
                state = HUNTING
                log("[TRANSITION] -> HUNTING (Cooldown Finished)")

        except Exception as e:
            log(f"FSM Error: {e}")
            time.sleep(60)

if __name__ == '__main__':
    run_v2_daemon()