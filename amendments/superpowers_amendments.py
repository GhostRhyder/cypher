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
MIN_VOLUME_USDT = 5_000_000

# Maximum allowed spread (bid/ask) as a fraction
MAX_SPREAD_PCT = 0.0015     # 0.15%

# ADX thresholds
ADX_TRENDING = 25           # above this = trending market
ADX_RANGING  = 20           # below this = choppy/ranging market

# ATR spike — if current ATR > median * this multiplier = high volatility
ATR_SPIKE_MULT = 1.8

# Base fallback parameters (neutral regime)
BASE_TP = 0.008             # 0.8%
BASE_SL = 0.005             # 0.5%


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
    """
    Returns (current_atr, median_atr).
    True Range = max(high-low, |high-prev_close|, |low-prev_close|)
    Uses Wilder smoothing — same as TradingView.
    """
    if len(klines) < period + 1:
        return 0.0, 0.0

    # Pionex kline format: [time, open, close, high, low, volume]
    closes = [float(k[2]) for k in klines]
    highs  = [float(k[3]) for k in klines]
    lows   = [float(k[4]) for k in klines]

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
    """
    ADX (Average Directional Index).
    >25 = trending, <20 = ranging/choppy.
    Uses Wilder smoothing — same as TradingView.
    """
    if len(klines) < period * 2:
        return 0.0

    # Pionex kline format: [time, open, close, high, low, volume]
    closes = [float(k[2]) for k in klines]
    highs  = [float(k[3]) for k in klines]
    lows   = [float(k[4]) for k in klines]

    plus_dm_list  = []
    minus_dm_list = []
    tr_list       = []

    for i in range(1, len(klines)):
        up_move   = highs[i]  - highs[i-1]
        down_move = lows[i-1] - lows[i]

        plus_dm  = up_move   if (up_move > down_move  and up_move > 0)   else 0.0
        minus_dm = down_move if (down_move > up_move  and down_move > 0) else 0.0

        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i]  - closes[i-1])
        )
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
        if sm_tr[i] == 0:
            continue
        plus_di  = 100 * sm_plus[i]  / sm_tr[i]
        minus_di = 100 * sm_minus[i] / sm_tr[i]
        denom    = plus_di + minus_di
        if denom == 0:
            continue
        dx_list.append(100 * abs(plus_di - minus_di) / denom)

    if len(dx_list) < period:
        return 0.0

    return float(np.mean(dx_list[-period:]))


def calc_spread(ob: dict) -> float:
    """Spread as a fraction of mid price from orderbook."""
    try:
        best_ask = float(ob["asks"][0][0])
        best_bid = float(ob["bids"][0][0])
        mid      = (best_ask + best_bid) / 2
        return (best_ask - best_bid) / mid
    except Exception:
        return 0.0


# ── Regime Detection ──────────────────────────────────────────────────────────

def detect_regime(symbol: str, send_pionex_request, get_candles) -> MarketRegime:
    """
    Classifies the current market regime for a symbol.
    Uses Cypher's existing send_pionex_request and get_candles functions
    so we don't duplicate API auth logic.
    """
    # Candles — 5m, 100 bars
    klines = []
    try:
        resp = get_candles(symbol, "5M", limit=100)
        if resp and 'data' in resp and 'klines' in resp['data']:
            klines = resp['data']['klines']
    except Exception as e:
        print(f"[Superpowers] Candle fetch error {symbol}: {e}")

    # Orderbook for spread
    ob = {}
    try:
        res = send_pionex_request("GET", "/api/v1/market/depth", params={"symbol": symbol, "limit": 5})
        if res and 'data' in res:
            ob = res['data']
    except Exception as e:
        print(f"[Superpowers] Orderbook error {symbol}: {e}")

    # 24h volume
    volume = 0.0
    try:
        res = send_pionex_request("GET", "/api/v1/market/tickers")
        for t in res.get('data', {}).get('tickers', []):
            if t.get('symbol') == symbol:
                volume = float(t.get('amount', 0))
                break
    except Exception as e:
        print(f"[Superpowers] Volume error {symbol}: {e}")

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


# ── Adaptive Parameter Engine ─────────────────────────────────────────────────

def get_trade_params(symbol: str, _send_pionex_request=None, _get_candles=None) -> TradeParams:
    """
    ──────────────────────────────────────────────────────
    MAIN ENTRY POINT — called by trade_daemon_v2 before
    every single entry.

    Two calling modes:

    1. Standalone (pass API functions explicitly):
         from superpowers import get_trade_params
         from pionex_api_template import send_pionex_request, get_candles
         params = get_trade_params("SOL_USDT", send_pionex_request, get_candles)

    2. Auto-import (daemon passes nothing, we import internally):
         params = get_trade_params("SOL_USDT")
    ──────────────────────────────────────────────────────
    """
    # If caller didn't pass API functions, import them ourselves
    if _send_pionex_request is None or _get_candles is None:
        try:
            from pionex_api_template import send_pionex_request as spr, get_candles as gc
            _send_pionex_request = spr
            _get_candles = gc
        except ImportError as e:
            # Can't reach API — return safe neutral params rather than crash
            print(f"[Superpowers] API import failed: {e}. Using base params.")
            return TradeParams(
                trade=True, tp_pct=BASE_TP, sl_pct=BASE_SL,
                trail=False, trail_act=0, trail_dist=0,
                size_mult=0.75, regime="neutral",
                reason="API unavailable — base params applied"
            )

    r = detect_regime(symbol, _send_pionex_request, _get_candles)

    # ── Hard skip: no liquidity ───────────────────────
    if not r.has_liquidity:
        return TradeParams(
            trade=False, tp_pct=0, sl_pct=0,
            trail=False, trail_act=0, trail_dist=0,
            size_mult=0, regime="skip",
            reason=f"Volume ${r.volume_usdt:,.0f} below ${MIN_VOLUME_USDT:,.0f} minimum"
        )

    # ── Hard skip: spread too wide ────────────────────
    if not r.spread_ok:
        return TradeParams(
            trade=False, tp_pct=0, sl_pct=0,
            trail=False, trail_act=0, trail_dist=0,
            size_mult=0, regime="skip",
            reason=f"Spread {r.spread_pct*100:.3f}% exceeds {MAX_SPREAD_PCT*100:.2f}% limit"
        )

    # ── Volatile: ATR spike detected ──────────────────
    if r.is_volatile:
        return TradeParams(
            trade=True,
            tp_pct=0.015,       # 1.5% — needs room to breathe
            sl_pct=0.008,       # 0.8% — wider floor
            trail=False,        # trail gets whipsawed in spikes
            trail_act=0,
            trail_dist=0,
            size_mult=0.5,      # half size — protect capital
            regime="volatile",
            reason=f"ATR spike {r.atr:.6f} vs median {r.atr_median:.6f} — half size"
        )

    # ── Trending: ADX strong ──────────────────────────
    if r.is_trending:
        return TradeParams(
            trade=True,
            tp_pct=0.012,       # 1.2% — let winners run
            sl_pct=0.006,       # 0.6% — slightly wider
            trail=True,         # trail is VALID in trends
            trail_act=0.010,    # activate at +1.0%
            trail_dist=0.004,   # shadow 0.4% behind peak
            size_mult=1.0,      # full size — high conviction
            regime="trending",
            reason=f"ADX {r.adx:.1f} — trending. Full size, trail on."
        )

    # ── Ranging: choppy conditions ────────────────────
    if r.is_ranging:
        return TradeParams(
            trade=True,
            tp_pct=0.006,       # 0.6% — take what's there
            sl_pct=0.004,       # 0.4% — tight
            trail=False,        # NO trail — chop kills it
            trail_act=0,
            trail_dist=0,
            size_mult=0.75,     # slightly reduced
            regime="ranging",
            reason=f"ADX {r.adx:.1f} — ranging. Tight TP/SL, no trail."
        )

    # ── Neutral: transitioning / unclear ─────────────
    return TradeParams(
        trade=True,
        tp_pct=BASE_TP,
        sl_pct=BASE_SL,
        trail=False,
        trail_act=0,
        trail_dist=0,
        size_mult=0.75,
        regime="neutral",
        reason=f"ADX {r.adx:.1f} — no clear regime. Base params, reduced size."
    )