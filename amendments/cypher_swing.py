"""
cypher_swing.py — Momentum Swing Strategy Module
=================================================
Companion module to trade_daemon_v3.py and superpowers.py.
Runs on 4H candles, targets 2-4% moves, holds hours to overnight.

Designed to run ALONGSIDE the 5m scalper — separate capital pool,
separate position tracker, same Pionex API.

ENTRY:  StochRSI 4H oversold + MACD histogram cross + volume confirmation
EXIT:   Fixed TP / trailing stop / time exit (48h max)

Usage:
    from cypher_swing import SwingDaemon
    swing = SwingDaemon()
    swing.run()
"""

import time
import json
import talib
import numpy as np
import pandas as pd
from datetime import datetime
from dataclasses import dataclass
from pionex_api_template import send_pionex_request, get_candles

# ── Config ────────────────────────────────────────────────────────────────────

SWING_LOG_FILE      = "swing_daemon.log"
SWING_STATE_FILE    = "swing_state.json"
SWING_HISTORY_FILE  = "swing_history.json"

# Capital
MAX_SWING_POSITIONS = 2        # Only 2 concurrent — holds are longer
MIN_SWING_SIZE      = 20.0     # Minimum trade size USDT
SWING_CAPITAL_POOL  = 60.0     # Max USDT allocated to swing trades total

# Exit parameters (adjusted by regime via superpowers)
BASE_SWING_TP       = 0.025    # +2.5% take profit
BASE_SWING_SL       = 0.015    # -1.5% stop loss
TRAIL_ACTIVATION    = 0.010    # Trail activates at +1.0%
TRAIL_DISTANCE      = 0.005    # Trails 0.5% behind peak
MAX_HOLD_CANDLES    = 12       # 12 x 4H = 48 hours max hold

# Signal thresholds
STOCHRSI_OVERSOLD   = 30       # StochRSI below this = oversold
MACD_CONFIRMATION   = True     # Require MACD histogram cross
VOLUME_MULT         = 1.2      # Volume must be > 1.2x 20-period average

# Universe — liquid coins suitable for 4H swings
SWING_UNIVERSE = [
    "BTC_USDT",
    "ETH_USDT",
    "SOL_USDT",
    "XRP_USDT",
    "ADA_USDT",
    "LINK_USDT",
    "AVAX_USDT",
    "BNB_USDT",
]

# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class SwingSignal:
    symbol:        str
    signal_type:   str          # "oversold_bounce" or "momentum_break"
    stoch_k:       float
    stoch_d:       float
    macd_hist:     float
    volume_ratio:  float        # current vol vs 20-period avg
    entry_price:   float
    confidence:    str          # "high" / "medium"


@dataclass
class SwingPosition:
    symbol:        str
    entry:         float
    peak:          float
    quantity:      float
    cost_basis:    float
    start_time:    int
    candles_held:  int
    signal_type:   str
    tp_pct:        float
    sl_pct:        float
    trail_act:     float
    trail_dist:    float


# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str):
    stamp = (datetime.now() + pd.Timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    line  = f"[SWING] [{stamp}] {msg}"
    print(line)
    with open(SWING_LOG_FILE, "a") as f:
        f.write(line + "\n")


# ── API Helpers ───────────────────────────────────────────────────────────────

def get_4h_candles(symbol: str, limit: int = 100) -> pd.DataFrame | None:
    """Fetch 4H OHLCV candles and return as DataFrame."""
    try:
        resp = get_candles(symbol, "4H", limit=limit)
        if not resp or 'data' not in resp or 'klines' not in resp['data']:
            return None
        klines = resp['data']['klines']
        if not klines or len(klines) < 50:
            return None
        df = pd.DataFrame(
            klines,
            columns=['time', 'open', 'close', 'high', 'low', 'volume']
        )
        for col in ['open', 'close', 'high', 'low', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)
        return df
    except Exception as e:
        log(f"Candle fetch error {symbol}: {e}")
        return None


def get_ticker(symbol: str) -> float | None:
    try:
        res = send_pionex_request("GET", "/api/v1/market/tickers", params={"symbol": symbol})
        return float(res['data']['tickers'][0]['close'])
    except:
        return None


def get_usdt_balance() -> float:
    try:
        res = send_pionex_request("GET", "/api/v1/account/balances")
        for item in res['data']['balances']:
            if item['coin'] == 'USDT':
                return float(item['free'])
        return 0.0
    except:
        return 0.0


def get_coin_balance(symbol: str) -> float:
    try:
        coin = symbol.split('_')[0]
        res  = send_pionex_request("GET", "/api/v1/account/balances")
        for item in res['data']['balances']:
            if item['coin'] == coin:
                return float(item['free'])
        return 0.0
    except:
        return 0.0


# ── Signal Detection ──────────────────────────────────────────────────────────

def detect_swing_signal(symbol: str) -> SwingSignal | None:
    """
    Scan a symbol for 4H momentum swing entry.
    Returns SwingSignal if entry criteria met, None if not.

    Two signal types:
    1. oversold_bounce — StochRSI < 30, crossing up, MACD confirming
    2. momentum_break  — MACD cross up from negative, RSI > 50, volume spike
    """
    df = get_4h_candles(symbol)
    if df is None:
        return None

    close  = df['close'].values
    high   = df['high'].values
    low    = df['low'].values
    volume = df['volume'].values

    # ── Indicators ────────────────────────────────────
    try:
        fastk, fastd = talib.STOCHRSI(
            close, timeperiod=14,
            fastk_period=3, fastd_period=3, fastd_matype=0
        )
    except Exception as e:
        log(f"StochRSI error {symbol}: {e}")
        return None

    try:
        macd, macd_signal, macd_hist = talib.MACD(
            close, fastperiod=12, slowperiod=26, signalperiod=9
        )
        rsi = talib.RSI(close, timeperiod=14)
    except Exception as e:
        log(f"MACD/RSI error {symbol}: {e}")
        return None

    # ── Volume ratio ───────────────────────────────────
    if len(volume) < 20:
        return None
    vol_avg    = np.mean(volume[-20:])
    vol_ratio  = volume[-1] / vol_avg if vol_avg > 0 else 0

    entry_price = close[-1]
    k, d         = fastk[-1], fastd[-1]
    k_prev, d_prev = fastk[-2], fastd[-2]
    hist_curr    = macd_hist[-1]
    hist_prev    = macd_hist[-2]

    # ── Signal 1: Oversold Bounce ──────────────────────
    # StochRSI < 30, K crosses above D, MACD histogram turning positive
    oversold_bounce = (
        k < STOCHRSI_OVERSOLD
        and k > d                       # K crossed above D (bullish)
        and k_prev <= d_prev            # Was below on last candle
        and hist_curr > hist_prev       # MACD histogram rising
        and vol_ratio >= VOLUME_MULT    # Volume confirmation
    )

    if oversold_bounce:
        confidence = "high" if hist_curr > 0 else "medium"
        log(f"[SIGNAL] 🟢 Oversold Bounce on {symbol} | "
            f"K:{k:.1f} D:{d:.1f} | Vol:{vol_ratio:.2f}x | "
            f"Confidence: {confidence}")
        return SwingSignal(
            symbol=symbol,
            signal_type="oversold_bounce",
            stoch_k=k,
            stoch_d=d,
            macd_hist=hist_curr,
            volume_ratio=vol_ratio,
            entry_price=entry_price,
            confidence=confidence
        )

    # ── Signal 2: Momentum Breakout ────────────────────
    # MACD histogram crosses from negative to positive
    # RSI > 50 (momentum already building)
    # Volume spike confirms breakout
    momentum_break = (
        hist_curr > 0                   # MACD histogram just went positive
        and hist_prev <= 0              # Was negative before
        and rsi[-1] > 50                # Price momentum already building
        and vol_ratio >= VOLUME_MULT    # Volume conviction
        and k > 40                      # Not already overbought on StochRSI
    )

    if momentum_break:
        log(f"[SIGNAL] 🔵 Momentum Break on {symbol} | "
            f"RSI:{rsi[-1]:.1f} | Vol:{vol_ratio:.2f}x | "
            f"MACD hist: {hist_prev:.6f} → {hist_curr:.6f}")
        return SwingSignal(
            symbol=symbol,
            signal_type="momentum_break",
            stoch_k=k,
            stoch_d=d,
            macd_hist=hist_curr,
            volume_ratio=vol_ratio,
            entry_price=entry_price,
            confidence="medium"
        )

    return None


def scan_swing_universe(exclude_symbols: list) -> SwingSignal | None:
    """
    Scan all coins in SWING_UNIVERSE for entry signals.
    Returns first valid signal found.
    """
    for symbol in SWING_UNIVERSE:
        if symbol in exclude_symbols:
            continue
        signal = detect_swing_signal(symbol)
        if signal:
            return signal
        time.sleep(0.3)  # Rate limiting
    return None


# ── Execution ─────────────────────────────────────────────────────────────────

def execute_buy(symbol: str, usdt_amount: float) -> bool:
    try:
        body = {
            "symbol": symbol,
            "side":   "BUY",
            "type":   "MARKET",
            "amount": f"{usdt_amount:.2f}"
        }
        log(f"[ORDER] BUY {symbol} ${usdt_amount:.2f}")
        resp = send_pionex_request("POST", "/api/v1/trade/order", body=body)
        if resp.get('result'):
            log(f"[ORDER] ✅ BUY confirmed {symbol}")
            return True
        log(f"[ORDER] ❌ BUY failed: {resp}")
        return False
    except Exception as e:
        log(f"[ORDER] Exception buying {symbol}: {e}")
        return False


def execute_sell(symbol: str) -> bool:
    try:
        coin    = symbol.split('_')[0]
        res     = send_pionex_request("GET", "/api/v1/account/balances")
        balance = 0.0
        for b in res['data']['balances']:
            if b['coin'] == coin:
                balance = float(b['free'])
                break

        if balance <= 0:
            log(f"[ORDER] No balance to sell for {symbol}")
            return False

        sym_res   = send_pionex_request("GET", "/api/v1/common/symbols")
        base_prec = 4
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
            log(f"[ORDER] ✅ SELL confirmed {symbol} size {size_str}")
            return True
        return False
    except Exception as e:
        log(f"[ORDER] Exception selling {symbol}: {e}")
        return False


# ── History & State ───────────────────────────────────────────────────────────

def save_trade(pos: SwingPosition, exit_price: float, exit_reason: str):
    pnl_pct  = (exit_price - pos.entry) / pos.entry * 100
    pnl_usdt = pos.cost_basis * (pnl_pct / 100)

    trade = {
        "timestamp":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "strategy":     "swing",
        "symbol":       pos.symbol,
        "signal_type":  pos.signal_type,
        "entry":        pos.entry,
        "exit":         exit_price,
        "pnl_pct":      round(pnl_pct, 4),
        "pnl_usdt":     round(pnl_usdt, 4),
        "cost_basis":   pos.cost_basis,
        "candles_held": pos.candles_held,
        "exit_reason":  exit_reason,
        "result":       "WIN" if pnl_pct >= 0 else "LOSS"
    }

    try:
        with open(SWING_HISTORY_FILE, "r") as f:
            history = json.load(f)
    except:
        history = []

    history.append(trade)
    with open(SWING_HISTORY_FILE, "w") as f:
        json.dump(history[-5000:], f, indent=2)

    log(f"[HISTORY] {pos.symbol} {trade['result']} | "
        f"PnL: {pnl_pct:+.2f}% (${pnl_usdt:+.2f}) | "
        f"Held: {pos.candles_held} candles | Reason: {exit_reason}")


def save_swing_state(positions: dict):
    data = {
        "updated":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "positions": [
            {
                "symbol":       p.symbol,
                "entry":        p.entry,
                "peak":         p.peak,
                "quantity":     p.quantity,
                "cost_basis":   p.cost_basis,
                "start_time":   p.start_time,
                "candles_held": p.candles_held,
                "signal_type":  p.signal_type,
                "tp_pct":       p.tp_pct,
                "sl_pct":       p.sl_pct,
            }
            for p in positions.values()
        ]
    }
    with open(SWING_STATE_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── Main Daemon ───────────────────────────────────────────────────────────────

class SwingDaemon:
    """
    Runs alongside the scalp daemon in a separate process or thread.

    Usage:
        from cypher_swing import SwingDaemon
        daemon = SwingDaemon()
        daemon.run()

    Or in a thread alongside the scalp daemon:
        import threading
        from cypher_swing import SwingDaemon
        swing = SwingDaemon()
        t = threading.Thread(target=swing.run, daemon=True)
        t.start()
    """

    def __init__(self):
        self.active_positions: dict[str, SwingPosition] = {}
        self.last_candle_check = 0   # Unix timestamp of last 4H scan
        self.candle_interval   = 4 * 60 * 60  # 4 hours in seconds

    def _is_4h_candle_close(self) -> bool:
        """
        Only scan for new entries on 4H candle closes.
        This prevents re-scanning mid-candle and false signals.
        """
        now     = int(time.time())
        elapsed = now - self.last_candle_check
        if elapsed >= self.candle_interval:
            self.last_candle_check = now
            return True
        return False

    def _monitor_positions(self):
        """Check all open positions for exit conditions."""
        for symbol in list(self.active_positions.keys()):
            pos           = self.active_positions[symbol]
            current_price = get_ticker(symbol)
            if not current_price:
                continue

            # Track peak
            if current_price > pos.peak:
                pos.peak = current_price

            profit_pct  = (current_price - pos.entry) / pos.entry
            should_exit = False
            reason      = ""

            # ── Stop Loss ─────────────────────────────
            if profit_pct <= -pos.sl_pct:
                reason      = f"STOP LOSS {profit_pct*100:.2f}%"
                should_exit = True

            # ── Take Profit ───────────────────────────
            elif profit_pct >= pos.tp_pct:
                # TP hit — now switch to trailing to squeeze more
                if pos.peak >= pos.entry * (1 + pos.trail_act):
                    if current_price <= pos.peak * (1 - pos.trail_dist):
                        reason      = f"TRAIL EXIT {profit_pct*100:.2f}% (Peak: {pos.peak:.6f})"
                        should_exit = True
                else:
                    reason      = f"TAKE PROFIT {profit_pct*100:.2f}%"
                    should_exit = True

            # ── Time Exit — max 12 x 4H candles ──────
            elif pos.candles_held >= MAX_HOLD_CANDLES:
                reason      = f"TIME EXIT after {pos.candles_held} candles ({profit_pct*100:.2f}%)"
                should_exit = True

            if should_exit:
                log(f"[EXIT] {symbol}: {reason}")
                if execute_sell(symbol):
                    save_trade(pos, current_price, reason)
                    del self.active_positions[symbol]

    def _hunt_entries(self):
        """Scan for new swing entries on 4H candle close."""
        if len(self.active_positions) >= MAX_SWING_POSITIONS:
            return

        usdt = get_usdt_balance()
        # Don't use more than the allocated swing capital pool
        available = min(usdt, SWING_CAPITAL_POOL)

        position_size = available / MAX_SWING_POSITIONS
        trade_size    = max(MIN_SWING_SIZE, position_size)

        if usdt < trade_size:
            log(f"[HUNTING] Insufficient USDT (${usdt:.2f}) for swing trade (${trade_size:.2f})")
            return

        log(f"[HUNTING] Scanning 4H universe... "
            f"({len(self.active_positions)}/{MAX_SWING_POSITIONS} active)")

        signal = scan_swing_universe(
            exclude_symbols=list(self.active_positions.keys())
        )

        if not signal:
            log("[HUNTING] No signals this 4H candle.")
            return

        # Adjust confidence → position size
        if signal.confidence == "high":
            final_size = trade_size          # Full allocation
        else:
            final_size = trade_size * 0.75   # Medium confidence = 75%

        log(f"[SIGNAL] {signal.symbol} | {signal.signal_type} | "
            f"Confidence: {signal.confidence} | Size: ${final_size:.2f}")

        if execute_buy(signal.symbol, final_size):
            time.sleep(3)
            price = get_ticker(signal.symbol)
            qty   = get_coin_balance(signal.symbol)

            if price and qty > 0:
                self.active_positions[signal.symbol] = SwingPosition(
                    symbol=signal.symbol,
                    entry=price,
                    peak=price,
                    quantity=qty,
                    cost_basis=final_size,
                    start_time=int(time.time()),
                    candles_held=0,
                    signal_type=signal.signal_type,
                    tp_pct=BASE_SWING_TP,
                    sl_pct=BASE_SWING_SL,
                    trail_act=TRAIL_ACTIVATION,
                    trail_dist=TRAIL_DISTANCE,
                )
                log(f"[DEPLOYED] {signal.symbol} @ {price:.6f} | "
                    f"Signal: {signal.signal_type} | "
                    f"TP: {BASE_SWING_TP*100:.1f}% SL: {BASE_SWING_SL*100:.1f}%")

    def run(self):
        log("=" * 55)
        log("Cypher Swing Daemon starting. Universe: "
            f"{', '.join(SWING_UNIVERSE)}")
        log(f"Max positions: {MAX_SWING_POSITIONS} | "
            f"Capital pool: ${SWING_CAPITAL_POOL}")
        log("=" * 55)

        while True:
            try:
                # Always monitor open positions (every loop)
                self._monitor_positions()

                # Increment candle counter for open positions
                for pos in self.active_positions.values():
                    pos.candles_held = int(
                        (time.time() - pos.start_time) / self.candle_interval
                    )

                # Only hunt on 4H candle close
                if self._is_4h_candle_close():
                    self._hunt_entries()

                # Save state
                save_swing_state(self.active_positions)

                # Check every 5 minutes (position monitoring)
                time.sleep(300)

            except Exception as e:
                log(f"[ERROR] Loop error: {e}")
                time.sleep(60)


# ── Run standalone or import ──────────────────────────────────────────────────

if __name__ == "__main__":
    daemon = SwingDaemon()
    daemon.run()
