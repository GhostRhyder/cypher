from superpowers import get_trade_params
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
HUNTING     = "HUNTING"
DEPLOYED    = "DEPLOYED"
COMPOUNDING = "COMPOUNDING"
COOLDOWN    = "COOLDOWN"

# V3 Config
MAX_POSITIONS   = 3
MIN_TRADE_SIZE  = 15.0
HARD_STOP_PCT   = 0.005     # fallback only — superpowers overrides this
HARD_TP_PCT     = 0.008     # fallback only — superpowers overrides this
MAX_SPREAD_PCT  = 0.0015
COOLDOWN_MINUTES = 5

ALLOWED_COINS = [
    "BTC_USDT", "ETH_USDT", "SOL_USDT",
    "ADA_USDT", "TRX_USDT", "XRP_USDT",
    "LINK_USDT", "AVAX_USDT"
]

def log(msg):
    now_utc      = datetime.now()
    now_plus_one = now_utc + pd.Timedelta(hours=1)
    stamp        = now_plus_one.strftime("%Y-%m-%d %H:%M:%S")
    line         = f"[V3] [{stamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def save_state(state, active_positions=[], pnl=0.0):
    now_plus_one = datetime.now() + pd.Timedelta(hours=1)
    data = {
        "state":     state,
        "positions": active_positions,
        "timestamp": now_plus_one.strftime("%H:%M:%S"),
        "updated":   now_plus_one.strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)
    except:
        pass

def save_trade_history(coin, entry, exit_price, pnl_pct, cost_basis=21.50, start_time=None):
    now_plus_one = datetime.now() + pd.Timedelta(hours=1)
    pnl_pct_net  = pnl_pct - 0.2
    pnl_usdt     = cost_basis * (pnl_pct_net / 100.0)

    trade_len = "N/A"
    if start_time:
        secs      = int(time.time() - start_time)
        trade_len = f"{secs // 60}m"

    trade = {
        "timestamp":   now_plus_one.strftime("%Y-%m-%d %H:%M:%S"),
        "version":     "V3",
        "direction":   "LONG",
        "trade_length": trade_len,
        "coin":        coin,
        "entry":       entry,
        "exit":        exit_price,
        "pnl_pct":     pnl_pct_net,
        "pnl_usdt":    pnl_usdt,
        "cost_basis":  cost_basis,
        "result":      "WIN" if pnl_pct_net >= 0 else "LOSS"
    }

    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
    except:
        history = []

    history.append(trade)
    if len(history) > 10000:
        history = history[-10000:]

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
        res = send_pionex_request("GET", "/api/v1/market/tickers", params={"symbol": symbol})
        return float(res['data']['tickers'][0]['close'])
    except:
        return None

def get_top_volume_coins(limit=10):
    return ALLOWED_COINS

def get_spread_pct(symbol):
    try:
        res = send_pionex_request("GET", "/api/v1/market/depth", params={"symbol": symbol, "limit": 1})
        if res and 'data' in res:
            bid = float(res['data']['bids'][0][0])
            ask = float(res['data']['asks'][0][0])
            if bid > 0 and ask > 0:
                return (ask - bid) / bid
        return None
    except:
        return None

def scan_market(exclude_symbols=[]):
    top_coins = get_top_volume_coins()
    for symbol in top_coins:
        if symbol in exclude_symbols or symbol in FAILED_SYMBOLS:
            continue

        spread = get_spread_pct(symbol)
        if spread is None or spread > MAX_SPREAD_PCT:
            continue

        resp = get_candles(symbol, "5M", limit=100)
        if not resp or 'data' not in resp or 'klines' not in resp['data']:
            continue

        klines = resp['data']['klines']
        if not klines or len(klines) < 50:
            continue

        df          = pd.DataFrame(klines, columns=['time', 'open', 'close', 'high', 'low', 'volume'])
        df['close'] = pd.to_numeric(df['close']).astype(float)
        close       = df['close'].values

        # Signal: S5_Scalp — StochRSI cross up from oversold
        try:
            fastk, fastd = talib.STOCHRSI(close, timeperiod=14, fastk_period=3, fastd_period=3, fastd_matype=0)
            if fastk[-1] < 20 and fastk[-1] > fastd[-1] and fastk[-2] <= fastd[-2]:
                log(f"[SCANNER] 🔥 S5_Scalp on {symbol} (Spread: {spread*100:.3f}%)")
                return symbol
        except:
            pass

        # Signal: S4_Momentum — MACD cross with RSI > 50
        try:
            macd, macd_signal, _ = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
            rsi                  = talib.RSI(close, timeperiod=14)
            if macd[-1] > macd_signal[-1] and rsi[-1] > 50 and macd[-2] <= macd_signal[-2]:
                log(f"[SCANNER] 🔥 S4_Momentum on {symbol} (Spread: {spread*100:.3f}%)")
                return symbol
        except:
            pass

    return None

def execute_buy(symbol, usdt_amount):
    try:
        amt_str = f"{usdt_amount:.2f}"
        body    = {"symbol": symbol, "side": "BUY", "type": "MARKET", "amount": amt_str}
        log(f"[DEBUG] Placing BUY: {body}")
        resp = send_pionex_request("POST", "/api/v1/trade/order", body=body)
        if resp.get('result'):
            log(f"[EXECUTE] ✅ BUY {symbol} ${amt_str}")
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
    try:
        coin = symbol.split('_')[0]
        res  = send_pionex_request("GET", "/api/v1/account/balances")
        for item in res['data']['balances']:
            if item['coin'] == coin:
                return float(item['free'])
        return 0.0
    except:
        return 0.0

def execute_sell(symbol):
    try:
        coin    = symbol.split('_')[0]
        res     = send_pionex_request("GET", "/api/v1/account/balances")
        balance = 0.0
        for b in res['data']['balances']:
            if b['coin'] == coin:
                balance = float(b['free'])
                break

        if balance <= 0:
            return False

        sym_res    = send_pionex_request("GET", "/api/v1/common/symbols")
        base_prec  = 4
        for s in sym_res['data']['symbols']:
            if s['symbol'] == symbol:
                base_prec = int(s.get('basePrecision', 4))
                break

        if base_prec == 0:
            size_str = str(int(balance))
        else:
            multiplier = 10 ** base_prec
            size_str   = str(int(balance * multiplier) / multiplier)

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
    active_positions = {}
    log(f"Initialize V3 Auto-Compounder. Max: {MAX_POSITIONS} positions. Superpowers: ACTIVE ✅")

    # ── Resume open positions from state ─────────────
    try:
        prev_positions = {}
        try:
            with open(STATE_FILE, "r") as f:
                saved_state = json.load(f)
                if saved_state.get('positions'):
                    for p in saved_state['positions']:
                        prev_positions[p['coin']] = p
        except:
            pass

        res = send_pionex_request("GET", "/api/v1/account/balances")
        for item in res['data']['balances']:
            coin = item['coin']
            free = float(item['free'])
            if coin != 'USDT' and free > 0:
                symbol = f"{coin}_USDT"
                price  = get_ticker(symbol)
                if price:
                    value = free * price
                    if value > 10.0:
                        old_data    = prev_positions.get(symbol, {})
                        entry_price = old_data.get('entry_price', price)
                        start_time  = old_data.get('start_time', int(time.time()))

                        log(f"[RESUME] {symbol} (${value:.2f}, Qty: {free})")
                        active_positions[symbol] = {
                            'entry':      entry_price,
                            'peak':       price,
                            'quantity':   free,
                            'start_time': start_time,
                            'cost_basis': old_data.get('cost_basis', value),
                            # Resumed positions use base params — no regime data available
                            'tp_pct':     HARD_TP_PCT,
                            'sl_pct':     HARD_STOP_PCT,
                            'trail':      False,
                            'trail_act':  0,
                            'trail_dist': 0,
                            'regime':     'resumed'
                        }
    except Exception as e:
        log(f"Startup check failed: {e}")

    # ── Main loop ─────────────────────────────────────
    while True:
        try:
            # ── Monitor open positions ────────────────
            for symbol in list(active_positions.keys()):
                pos           = active_positions[symbol]
                current_price = get_ticker(symbol)
                if not current_price:
                    continue

                # Track new peak
                if current_price > pos['peak']:
                    pos['peak'] = current_price

                profit_pct = (current_price - pos['entry']) / pos['entry']

                tp_pct     = pos.get('tp_pct',     HARD_TP_PCT)
                sl_pct     = pos.get('sl_pct',     HARD_STOP_PCT)
                trail      = pos.get('trail',      False)
                trail_act  = pos.get('trail_act',  0)
                trail_dist = pos.get('trail_dist', 0)

                should_sell = False
                reason      = ""

                if profit_pct <= -sl_pct:
                    reason      = f"STOP LOSS ({profit_pct*100:.2f}%) [Regime: {pos.get('regime','?')}]"
                    should_sell = True

                elif trail and pos['peak'] >= pos['entry'] * (1 + trail_act):
                    # Trailing stop: price dropped trail_dist % from peak
                    if current_price <= pos['peak'] * (1 - trail_dist):
                        reason      = f"TRAIL STOP ({profit_pct*100:.2f}%) [Peak: {pos['peak']:.6f}]"
                        should_sell = True

                elif not trail and profit_pct >= tp_pct:
                    reason      = f"TAKE PROFIT ({profit_pct*100:.2f}%) [Regime: {pos.get('regime','?')}]"
                    should_sell = True

                if should_sell:
                    log(f"[SELL] {symbol}: {reason}")
                    if execute_sell(symbol):
                        save_trade_history(
                            symbol, pos['entry'], current_price,
                            profit_pct * 100, pos.get('cost_basis', 21.50),
                            pos.get('start_time')
                        )
                        del active_positions[symbol]

            # ── Hunt for new entries ──────────────────
            if len(active_positions) < MAX_POSITIONS:
                usdt = get_usdt_balance()

                # Total equity = USDT + value of open positions
                total_equity = usdt
                for sym in active_positions:
                    price = get_ticker(sym)
                    if price:
                        total_equity += active_positions[sym]['quantity'] * price

                target_size = total_equity / MAX_POSITIONS
                trade_size  = max(MIN_TRADE_SIZE, target_size)

                if usdt >= trade_size:
                    log(f"[HUNTING] {len(active_positions)}/{MAX_POSITIONS} active. "
                        f"Scan size: ${trade_size:.2f} (Equity: ${total_equity:.2f})")

                    # ── BUG FIX: was mis-indented in original ──
                    target = scan_market(exclude_symbols=list(active_positions.keys()))

                    if target:
                        # ── Superpowers regime check ───────────
                        params = get_trade_params(target)

                        if not params.trade:
                            log(f"[SUPERPOWERS] ⛔ Blocked {target}: {params.reason}")
                        else:
                            trade_size_adjusted = trade_size * params.size_mult
                            log(f"[SUPERPOWERS] ✅ {target} | Regime: {params.regime} | "
                                f"TP: {params.tp_pct*100:.1f}% SL: {params.sl_pct*100:.1f}% "
                                f"Trail: {params.trail} | Size: ${trade_size_adjusted:.2f}")

                            if execute_buy(target, trade_size_adjusted):
                                time.sleep(3)
                                price = get_ticker(target)
                                qty   = get_coin_balance(target)

                                if price and qty > 0:
                                    active_positions[target] = {
                                        'entry':      price,
                                        'peak':       price,
                                        'quantity':   qty,
                                        'start_time': int(time.time()),
                                        'cost_basis': trade_size_adjusted,
                                        'tp_pct':     params.tp_pct,
                                        'sl_pct':     params.sl_pct,
                                        'trail':      params.trail,
                                        'trail_act':  params.trail_act,
                                        'trail_dist': params.trail_dist,
                                        'regime':     params.regime
                                    }
                                    log(f"[DEPLOYED] {target} @ {price} | "
                                        f"Regime: {params.regime} | Reason: {params.reason}")

            # ── Save dashboard state ──────────────────
            dashboard_pos = []
            for sym, pos in active_positions.items():
                curr = get_ticker(sym) or pos['peak']
                pnl  = (curr - pos['entry']) / pos['entry'] * 100
                dashboard_pos.append({
                    "coin":          sym,
                    "entry_price":   pos['entry'],
                    "current_price": curr,
                    "highest_price": pos['peak'],
                    "pnl_pct":       pnl,
                    "amount_usdt":   pos['quantity'] * curr,
                    "cost_basis":    pos.get('cost_basis', pos['quantity'] * curr),
                    "start_time":    pos.get('start_time', int(time.time())),
                    "regime":        pos.get('regime', 'unknown'),
                    "tp_pct":        pos.get('tp_pct', HARD_TP_PCT),
                    "sl_pct":        pos.get('sl_pct', HARD_STOP_PCT),
                })

            state_status = "DEPLOYED" if active_positions else "HUNTING"
            save_state(state_status, active_positions=dashboard_pos)

            time.sleep(30)

        except Exception as e:
            log(f"[ERROR] Loop error: {e}")
            time.sleep(60)

if __name__ == '__main__':
    run_v2_daemon()