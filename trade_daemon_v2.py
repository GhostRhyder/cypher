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

FAILED_SYMBOLS = []

# FSM States
HUNTING = "HUNTING"
DEPLOYED = "DEPLOYED"
COMPOUNDING = "COMPOUNDING"
COOLDOWN = "COOLDOWN"

# Config (Adjusted per Ghost's parameters)
MAX_POSITIONS = 5          # Allow up to 5 concurrent trades
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

def scan_market(exclude_symbols=[]):
    """Scans top 10 coins on 5M for S5_Scalp or S4_Momentum. Returns best symbol or None."""
    top_coins = get_top_volume_coins(10)
    for symbol in top_coins:
        if symbol in exclude_symbols or symbol in FAILED_SYMBOLS:
            continue
            
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
            if resp.get('code') == 'TRADE_INVALID_SYMBOL':
                FAILED_SYMBOLS.append(symbol)
                log(f"[BLACKLIST] {symbol} added to session blacklist.")
            return False
    except Exception as e:
        log(f"[EXECUTE] Error buying {symbol}: {e}")
        return False

def get_coin_balance(symbol):
    """Returns the free balance of the base currency for a given symbol (e.g. PEPE_USDT -> PEPE)."""
    try:
        coin = symbol.split('_')[0]
        res = send_pionex_request("GET", "/api/v1/account/balances")
        for item in res['data']['balances']:
            if item['coin'] == coin:
                return float(item['free'])
        return 0.0
    except:
        return 0.0

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
    active_positions = {} # {symbol: {'entry': 1.0, 'peak': 1.0, 'amount_usdt': 15.0}}
    log(f"Initialize V2 Auto-Compounder (Multi-Trade). Max: {MAX_POSITIONS} Positions.")

    # Startup Resume Logic
    try:
        res = send_pionex_request("GET", "/api/v1/account/balances")
        for item in res['data']['balances']:
            coin = item['coin']
            free = float(item['free'])
            if coin != 'USDT' and free > 0:
                symbol = f"{coin}_USDT"
                price = get_ticker(symbol)
                if price:
                    value = free * price
                    if value > 10.0:
                        log(f"[RESUME] Found existing bag of {symbol} (${value:.2f}, Qty: {free}).")
                        active_positions[symbol] = {
                            'entry': price, 
                            'peak': price,
                            'quantity': free,
                            'start_time': int(time.time()),
                            'cost_basis': value
                        }
    except Exception as e:
        log(f"Startup check failed: {e}")

    while True:
        try:
            # 1. MONITOR ACTIVE POSITIONS
            current_holdings = list(active_positions.keys())
            for symbol in current_holdings:
                pos = active_positions[symbol]
                current_price = get_ticker(symbol)
                
                if not current_price: continue
                
                if current_price > pos['peak']:
                    pos['peak'] = current_price
                    
                profit_pct = (current_price - pos['entry']) / pos['entry']
                peak_pct = (pos['peak'] - pos['entry']) / pos['entry']
                drop_from_peak = (pos['peak'] - current_price) / pos['peak']
                
                # Dynamic Size Calculation
                current_value_usdt = pos['quantity'] * current_price
                
                # Check Exits
                should_sell = False
                reason = ""
                
                # Defense: Hard Stop Loss
                if profit_pct <= -HARD_STOP_PCT:
                    reason = f"HARD STOP ({profit_pct*100:.2f}%)"
                    should_sell = True
                # Offense: Trailing Stop
                elif peak_pct >= TRAIL_ACTIVATION and drop_from_peak >= TRAIL_DISTANCE:
                    reason = f"TRAILING STOP (Peak: {peak_pct*100:.2f}%)"
                    should_sell = True
                    
                if should_sell:
                    log(f"[SELL] {symbol}: {reason} (Qty: {pos['quantity']})")
                    if execute_sell(symbol):
                        save_trade_history(symbol, pos['entry'], current_price, profit_pct * 100)
                        del active_positions[symbol]
                        continue 
                
                # Log PnL periodically (every ~30s is fine)
                # log(f"[{symbol}] PnL: {profit_pct*100:.2f}% | Val: ${current_value_usdt:.2f}")
            
            # 2. HUNT FOR NEW TRADES
            if len(active_positions) < MAX_POSITIONS:
                usdt = get_usdt_balance()
                
                # Compounding Logic: Trade Size = MAX(25% of Total Equity, $15.00)
                total_equity = usdt
                for sym in active_positions:
                    # Use dynamic current value
                    total_equity += active_positions[sym]['quantity'] * get_ticker(sym)
                    
                target_size = total_equity * 0.25
                trade_size = max(MIN_TRADE_SIZE, target_size)
                
                # Check execution feasibility: Do we actually have the required free USDT?
                if usdt >= trade_size:
                    log(f"[HUNTING] Active: {len(active_positions)}/{MAX_POSITIONS}. Scan Size: ${trade_size:.2f} (Equity: ${total_equity:.2f})")
                    
                    target = scan_market(exclude_symbols=list(active_positions.keys()))
                    if target:
                        if execute_buy(target, trade_size):
                            # Sleep to let balance update
                            time.sleep(3)
                            price = get_ticker(target)
                            qty = get_coin_balance(target)
                            
                            if price and qty > 0:
                                active_positions[target] = {
                                    'entry': price,
                                    'peak': price,
                                    'quantity': qty,
                                    'start_time': int(time.time()),
                                    'cost_basis': trade_size
                                }
                                log(f"[DEPLOYED] Added {target} at {price} (Qty: {qty})")
                else:
                    pass # Hold fire. Free USDT is insufficient to meet the calculated Trade Size.
            
            # 3. UPDATE STATE FILE
            dashboard_pos = []
            for sym, pos in active_positions.items():
                curr = get_ticker(sym) or pos['peak']
                pnl = (curr - pos['entry']) / pos['entry'] * 100
                current_val = pos['quantity'] * curr
                dashboard_pos.append({
                    "coin": sym,
                    "entry_price": pos['entry'],
                    "current_price": curr,
                    "highest_price": pos['peak'],
                    "pnl_pct": pnl,
                    "amount_usdt": current_val,
                    "cost_basis": pos.get('cost_basis', current_val),
                    "start_time": pos.get('start_time', int(time.time()))
                })
            
            state_status = "DEPLOYED" if active_positions else "HUNTING"
            save_state(state_status, active_positions=dashboard_pos)
            
            time.sleep(30) 
            
        except Exception as e:
            log(f"Loop Error: {e}")
            time.sleep(60)

if __name__ == '__main__':
    run_v2_daemon()