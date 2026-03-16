"""
superpowers.py — Cypher Regime Detection & Adaptive Parameters
==============================================================
Replaces static TP/SL/trail with market-aware dynamic parameters.
Plugs directly into trade_daemon_v2.py via:

    from superpowers import get_trade_params

Called once before every entry. Returns TradeParams telling Cypher
exactly how to trade that symbol right now — or whether to skip it.
"""

import numpy as np
from dataclasses import dataclass
import time

# ── Configuration ─────────────────────────────────────────────────────────────

# Minimum 24h USDT volume to even consider a coin
MIN_VOLUME_USDT = 1_000_000

# Maximum allowed spread (bid/ask) as a fraction
MAX_SPREAD_PCT = 0.0015     # 0.15%

# ADX thresholds
ADX_TRENDING = 25           # above this = trending market
ADX_RANGING  = 20           # below this = choppy/ranging market

# ATR spike — if current ATR > median * this multiplier = high volatility
ATR_SPIKE_MULT = 1.8

# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class TradeParams:
    trade:      bool    # Should we enter this trade at all?
    tp_pct:     float   # Take profit % (e.g. 0.008 = 0.8%)
    sl_pct:     float   # Stop loss %
    trail:      bool    # Use trailing stop?
    trail_act:  float   # Activation threshold for trail
    trail_dist: float   # Distance trail follows behind peak
    size_mult:  float   # Position size multiplier (1.0 = full, 0.5 = half)
    regime:     str     # "trending" / "ranging" / "volatile" / "neutral" / "skip"
    reason:     str     # Human-readable explanation logged by daemon
    signal_type: str = None # S4_Momentum or S5_Scalp


@dataclass
class MarketRegime:
    adx:           float
    atr:           float
    atr_median:    float
    spread_pct:    float
    volume_usdt:   float
    is_trending:   bool
    is_ranging:    bool
    is_volatile:   bool
    has_liquidity: bool
    spread_ok:     bool


# ── Indicator Calculations ────────────────────────────────────────────────────

def calc_atr(klines: list, period: int = 14) -> tuple[float, float]:
    """Returns (current_atr, median_atr)."""
    if len(klines) < period + 1:
        return 0.0, 0.0

    closes, highs, lows = [], [], []
    for k in klines:
        if isinstance(k, dict):
            closes.append(float(k.get('close', 0)))
            highs.append(float(k.get('high', 0)))
            lows.append(float(k.get('low', 0)))
        else:
            closes.append(float(k[2]))
            highs.append(float(k[3]))
            lows.append(float(k[4]))

    true_ranges = []
    for i in range(1, len(klines)):
        tr = max(
            highs[i]  - lows[i],
            abs(highs[i]  - closes[i-1]),
            abs(lows[i]   - closes[i-1])
        )
        true_ranges.append(tr)

    atr = np.mean(true_ranges[:period])
    atr_values = [atr]
    for tr in true_ranges[period:]:
        atr = (atr * (period - 1) + tr) / period
        atr_values.append(atr)

    return float(atr_values[-1]), float(np.median(atr_values))


def calc_adx(klines: list, period: int = 14) -> float:
    """ADX Calculation."""
    if len(klines) < period * 2:
        return 0.0

    closes, highs, lows = [], [], []
    for k in klines:
        if isinstance(k, dict):
            closes.append(float(k.get('close', 0)))
            highs.append(float(k.get('high', 0)))
            lows.append(float(k.get('low', 0)))
        else:
            closes.append(float(k[2]))
            highs.append(float(k[3]))
            lows.append(float(k[4]))

    plus_dm_list  = []
    minus_dm_list = []
    tr_list       = []

    for i in range(1, len(klines)):
        up_move   = highs[i]  - highs[i-1]
        down_move = lows[i-1] - lows[i]
        plus_dm  = up_move   if (up_move > down_move  and up_move > 0)   else 0.0
        minus_dm = down_move if (down_move > up_move  and down_move > 0) else 0.0
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        plus_dm_list.append(plus_dm)
        minus_dm_list.append(minus_dm)
        tr_list.append(tr)

    def wilder_smooth(data, n):
        result = [sum(data[:n])]
        for val in data[n:]:
            result.append(result[-1] - result[-1] / n + val)
        return result

    sm_tr    = wilder_smooth(tr_list,       period)
    sm_plus  = wilder_smooth(plus_dm_list,  period)
    sm_minus = wilder_smooth(minus_dm_list, period)

    dx_list = []
    for i in range(len(sm_tr)):
        if sm_tr[i] == 0: continue
        plus_di  = 100 * sm_plus[i]  / sm_tr[i]
        minus_di = 100 * sm_minus[i] / sm_tr[i]
        denom    = plus_di + minus_di
        if denom == 0: continue
        dx_list.append(100 * abs(plus_di - minus_di) / denom)

    if len(dx_list) < period: return 0.0
    return float(np.mean(dx_list[-period:]))


def calc_spread(ob: dict) -> float:
    try:
        best_ask = float(ob["asks"][0][0])
        best_bid = float(ob["bids"][0][0])
        mid      = (best_ask + best_bid) / 2
        return (best_ask - best_bid) / mid
    except:
        return 0.0


# ── Regime Detection ──────────────────────────────────────────────────────────

def detect_regime(symbol: str, send_pionex_request, get_candles) -> MarketRegime:
    klines = []
    try:
        resp = get_candles(symbol, "5M", limit=100)
        if resp and 'data' in resp and 'klines' in resp['data']:
            klines = resp['data']['klines']
    except: pass

    ob = {}
    try:
        res = send_pionex_request("GET", "/api/v1/market/depth", params={"symbol": symbol, "limit": 5})
        if res and 'data' in res: ob = res['data']
    except: pass

    volume = 0.0
    try:
        res = send_pionex_request("GET", "/api/v1/market/tickers")
        for t in res.get('data', {}).get('tickers', []):
            if t.get('symbol') == symbol:
                volume = float(t.get('amount', 0))
                break
    except: pass

    adx             = calc_adx(klines) if len(klines) >= 28 else 0.0
    atr, atr_median = calc_atr(klines) if len(klines) >= 15 else (0.0, 0.0)
    spread_pct      = calc_spread(ob)

    return MarketRegime(
        adx=adx,
        atr=atr,
        atr_median=atr_median,
        spread_pct=spread_pct,
        volume_usdt=volume,
        is_trending=adx >= ADX_TRENDING,
        is_ranging=adx < ADX_RANGING,
        is_volatile=(atr > atr_median * ATR_SPIKE_MULT) if atr_median > 0 else False,
        has_liquidity=volume >= MIN_VOLUME_USDT,
        spread_ok=spread_pct <= MAX_SPREAD_PCT,
    )


# ── Global Optimization Table (Ghost, Mar 16 2026) ────────────────────────────

GHOST_CONFIG = {
    "BTC_USDT": {
        "S5_Scalp":    {"tp": 0.012, "sl": 0.010},
        "S4_Momentum": {"tp": 0.015, "sl": 0.006}, # Ghost Optimized S4
        "default":     {"tp": 0.009, "sl": 0.003}
    },
    "ETH_USDT": {
        "S4_Momentum": {"tp": 0.015, "sl": 0.005}, # Ghost Optimized S4
        "S5_Scalp":    {"tp": 0.010, "sl": 0.003}, # Ghost Optimized S5
        "default":     {"tp": 0.010, "sl": 0.005}
    },
    "SOL_USDT": {
        "S4_Momentum": {"tp": 0.011, "sl": 0.010}, # Ghost Optimized S4
        "S5_Scalp":    {"tp": 0.011, "sl": 0.003}, # Ghost Optimized S5
        "default":     {"tp": 0.009, "sl": 0.005}
    },
    "XRP_USDT": {
        "S4_Momentum": {"tp": 0.007, "sl": 0.006}, # Ghost Optimized S4
        "S5_Scalp":    {"tp": 0.015, "sl": 0.009}, # Ghost Optimized S5
        "default":     {"tp": 0.014, "sl": 0.009}
    },
    "ADA_USDT": {
        "S4_Momentum": {"tp": 0.015, "sl": 0.003}, # Ghost Optimized S4
        "S5_Scalp":    {"tp": 0.011, "sl": 0.007}, # Ghost Optimized S5
        "default":     {"tp": 0.008, "sl": 0.006}
    },
    "DOGE_USDT": {
        "S5_Scalp":    {"tp": 0.015, "sl": 0.003}, # Ghost Optimized S5
        "default":     {"tp": 0.008, "sl": 0.005}
    },
    "LINK_USDT": {
        "S4_Momentum": {"tp": 0.007, "sl": 0.006}, # Ghost Optimized S4
        "S5_Scalp":    {"tp": 0.015, "sl": 0.005}, # Ghost Optimized S5
        "default":     {"tp": 0.015, "sl": 0.007}
    },
    "AVAX_USDT": {
        "S4_Momentum": {"tp": 0.013, "sl": 0.009}, # Ghost Optimized S4
        "S5_Scalp":    {"tp": 0.005, "sl": 0.005}, # Ghost Optimized S5
        "default":     {"tp": 0.005, "sl": 0.005}
    },
}


# ── Adaptive Parameter Engine ─────────────────────────────────────────────────

def get_trade_params(symbol: str, _send_pionex_request=None, _get_candles=None, signal_type=None) -> TradeParams:
    if _send_pionex_request is None or _get_candles is None:
        try:
            from pionex_api_template import send_pionex_request as spr, get_candles as gc
            _send_pionex_request = spr
            _get_candles = gc
        except:
            return TradeParams(trade=False, tp_pct=0, sl_pct=0, trail=False, trail_act=0, trail_dist=0, size_mult=0, regime="error", reason="API unavailable")

    r = detect_regime(symbol, _send_pionex_request, _get_candles)

    # Hard checks
    if not r.has_liquidity:
        return TradeParams(trade=False, tp_pct=0, sl_pct=0, trail=False, trail_act=0, trail_dist=0, size_mult=0, regime="skip", reason="Low volume")
    if not r.spread_ok:
        return TradeParams(trade=False, tp_pct=0, sl_pct=0, trail=False, trail_act=0, trail_dist=0, size_mult=0, regime="skip", reason="Wide spread")

    # ── GHOST OPTIMIZED MODE (DEFAULT) ──────────────────
    if symbol in GHOST_CONFIG:
        coin_config = GHOST_CONFIG[symbol]
        
        # Determine specific config based on signal type
        if signal_type and signal_type in coin_config:
            config = coin_config[signal_type]
            reason_signal = f"[{signal_type}]"
        else:
            config = coin_config.get("default", list(coin_config.values())[0])
            reason_signal = "[Default]"
        
        # If volatile, we still reduce size but keep your targets
        size = 1.0
        regime = "ghost_optimized"
        reason = f"Ghost Parameters Applied {reason_signal}: {config['tp']*100:.2f}% TP / {config['sl']*100:.2f}% SL"

        if r.is_volatile:
            size = 0.5
            regime = "ghost_volatile"
            reason += " (Volatile Market: Size 0.5x)"
        
        return TradeParams(
            trade=True,
            tp_pct=config['tp'],
            sl_pct=config['sl'],
            trail=False,
            trail_act=0,
            trail_dist=0,
            size_mult=size,
            regime=regime,
            reason=reason,
            signal_type=signal_type
        )

    # Fallback for non-optimized coins (Neutral/Trending logic)
    if r.is_trending:
        return TradeParams(trade=True, tp_pct=0.012, sl_pct=0.006, trail=True, trail_act=0.010, trail_dist=0.004, size_mult=1.0, regime="trending", reason="ADX trending")
    
    return TradeParams(trade=True, tp_pct=0.008, sl_pct=0.005, trail=False, trail_act=0, trail_dist=0, size_mult=0.75, regime="neutral", reason="Default fallback")
