"""
cypher_spotter.py — Cypher Trade Spotter
=========================================
Scans the Pionex futures universe for trend and range setups.
Writes results to trades.json which the dashboard reads.

Designed for MANUAL trading support — Cypher spots, Ghost decides.

Features:
  - Scans top futures pairs on longer timeframes (4H, 1D)
  - Identifies trend breakout setups (max 3)
  - Identifies range/sideways setups (max 3)
  - Calculates entry, TP, SL, R:R for each
  - Writes thesis and signal tags
  - Auto-expires trades after 4H (or 1D for daily setups)
  - Runs on a schedule — scan every 30 minutes

Usage:
    python3 cypher_spotter.py              # Scan once and write
    python3 cypher_spotter.py --watch      # Continuous, rescan every 30min
    python3 cypher_spotter.py --dashboard  # Open dashboard after scan
"""

import os
import sys
import json
import time
import argparse
import requests
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

try:
    import talib
except ImportError:
    print("ERROR: TA-Lib not installed. Run installation protocol.")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────

OUTPUT_FILE     = "trades.json"
SCAN_INTERVAL   = 1800          # 30 minutes
TRADE_EXPIRY_4H = 4 * 3600      # 4 hour expiry for 4H setups
TRADE_EXPIRY_1D = 24 * 3600     # 24 hour expiry for 1D setups

# Pionex futures universe — pairs with good liquidity
UNIVERSE = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
    "XRPUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT",
    "DOTUSDT", "DOGEUSDT", "MATICUSDT", "LTCUSDT",
    "ATOMUSDT", "UNIUSDT", "AAVEUSDT", "NEARUSDT",
    "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT",
]

# Minimum R:R to include a trade idea
MIN_RR          = 1.8

# Minimum confidence score to include
MIN_CONFIDENCE  = 0.60

# Binance API (public, no auth needed for market data)
BINANCE_BASE    = "https://api.binance.com"


# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class TradeIdea:
    coin:        str
    type:        str          # "LONG" / "SHORT" / "RANGE"
    timeframe:   str          # "4H" / "1D"
    entry:       str
    tp:          str
    sl:          str
    tp_pct:      str
    sl_pct:      str
    rr:          str
    confidence:  str
    thesis:      str
    signals:     list
    active:      list         # Which signals are currently firing
    posted:      str          # Human-readable time ago
    expires:     str          # Human-readable expiry
    posted_ts:   int          # Unix timestamp for expiry calc
    expiry_ts:   int          # Unix timestamp of expiry
    spark:       list         # Mini price history for sparkline


# ── Market Data ───────────────────────────────────────────────────────────────

def get_klines(symbol: str, interval: str, limit: int = 100) -> list:
    """Fetch OHLCV data from Binance public API."""
    try:
        resp = requests.get(
            f"{BINANCE_BASE}/api/v3/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            timeout=10
        )
        resp.raise_for_status()
        return [[
            int(k[0]),      # timestamp
            float(k[1]),    # open
            float(k[2]),    # high
            float(k[3]),    # low
            float(k[4]),    # close
            float(k[5]),    # volume
        ] for k in resp.json()]
    except Exception as e:
        return []


def get_24h_volume(symbol: str) -> float:
    """Get 24h trading volume in USDT."""
    try:
        resp = requests.get(
            f"{BINANCE_BASE}/api/v3/ticker/24hr",
            params={"symbol": symbol},
            timeout=5
        )
        return float(resp.json().get("quoteVolume", 0))
    except:
        return 0


def format_price(price: float, ref: float) -> str:
    """Format price with appropriate decimal places."""
    if ref < 0.01:
        return f"{price:.6f}"
    elif ref < 1:
        return f"{price:.4f}"
    elif ref < 100:
        return f"{price:.2f}"
    else:
        return f"{price:.1f}"


def time_ago(ts: int) -> str:
    """Convert timestamp to human-readable 'X min ago'."""
    delta = int(time.time()) - ts
    if delta < 3600:
        return f"{delta // 60} min ago"
    return f"{delta // 3600}h {(delta % 3600) // 60}m ago"


def time_remaining(expiry_ts: int) -> str:
    """Convert expiry timestamp to human-readable remaining time."""
    delta = expiry_ts - int(time.time())
    if delta <= 0:
        return "EXPIRED"
    if delta >= 86400:
        return "DAILY"
    h = delta // 3600
    m = (delta % 3600) // 60
    return f"{h}h {m}m"


def make_sparkline(closes: np.ndarray, n: int = 20) -> list:
    """Generate normalised sparkline data."""
    if len(closes) < n:
        return [5] * n
    data   = closes[-n:]
    mn, mx = data.min(), data.max()
    if mx == mn:
        return [5] * n
    return [round(float((v - mn) / (mx - mn) * 10), 1) for v in data]


# ── Trend Scanner ─────────────────────────────────────────────────────────────

class TrendScanner:
    """
    Finds trend breakout and momentum setups.
    Looks for: EMA alignment, MACD cross, RSI momentum,
               wedge/channel breaks, strong directional moves.
    """

    def scan(self, symbol: str) -> TradeIdea | None:
        """Scan a symbol for trend setup. Returns TradeIdea or None."""

        # Try 4H first, fall back to 1D for less active coins
        for timeframe in ["4h", "1d"]:
            klines = get_klines(symbol, timeframe, limit=100)
            if len(klines) < 50:
                continue

            result = self._analyse(symbol, klines, timeframe.upper())
            if result:
                return result

        return None

    def _analyse(
        self, symbol: str, klines: list, timeframe: str
    ) -> TradeIdea | None:

        closes  = np.array([k[4] for k in klines], dtype=float)
        highs   = np.array([k[2] for k in klines], dtype=float)
        lows    = np.array([k[3] for k in klines], dtype=float)
        volumes = np.array([k[5] for k in klines], dtype=float)

        price   = closes[-1]

        try:
            ema20       = talib.EMA(closes, 20)
            ema50       = talib.EMA(closes, 50)
            _, _, hist  = talib.MACD(closes, 12, 26, 9)
            rsi         = talib.RSI(closes, 14)
            adx         = talib.ADX(highs, lows, closes, 14)

            # Strip NaNs
            hist_c = hist[~np.isnan(hist)]
            rsi_c  = rsi[~np.isnan(rsi)]
            adx_c  = adx[~np.isnan(adx)]
            e20_c  = ema20[~np.isnan(ema20)]
            e50_c  = ema50[~np.isnan(ema50)]

            if len(hist_c) < 3 or len(rsi_c) < 2:
                return None

        except Exception as e:
            return None

        # ── Signal checks ──────────────────────────────────
        signals      = []
        active       = []
        signal_score = 0

        # 1. EMA alignment (bullish stack)
        if len(e20_c) >= 1 and len(e50_c) >= 1:
            if price > e20_c[-1] > e50_c[-1]:
                signals.append("EMA STACK")
                active.append("EMA STACK")
                signal_score += 0.25

        # 2. MACD cross up
        if hist_c[-1] > 0 and hist_c[-2] <= 0:
            signals.append("MACD CROSS")
            active.append("MACD CROSS")
            signal_score += 0.30
        elif hist_c[-1] > hist_c[-2] > hist_c[-3]:
            signals.append("MACD RISE")
            active.append("MACD RISE")
            signal_score += 0.15

        # 3. RSI momentum
        if len(rsi_c) >= 1:
            if 52 <= rsi_c[-1] <= 70:
                signals.append("RSI MOMENTUM")
                active.append("RSI MOMENTUM")
                signal_score += 0.20
            elif rsi_c[-1] > 70:
                signals.append("RSI HIGH")

        # 4. Volume spike
        vol_avg = np.mean(volumes[-21:-1])
        if vol_avg > 0 and volumes[-1] > vol_avg * 1.5:
            signals.append("VOL SURGE")
            active.append("VOL SURGE")
            signal_score += 0.15

        # 5. Trend strength (ADX)
        if len(adx_c) >= 1:
            if adx_c[-1] > 25:
                signals.append(f"ADX {adx_c[-1]:.0f}")
                active.append(f"ADX {adx_c[-1]:.0f}")
                signal_score += 0.10
            else:
                signals.append(f"ADX {adx_c[-1]:.0f}")

        # 6. Higher highs check (last 5 candles)
        recent_highs = highs[-5:]
        if all(recent_highs[i] >= recent_highs[i-1] for i in range(1, 5)):
            signals.append("HIGHER HIGHS")
            active.append("HIGHER HIGHS")
            signal_score += 0.10

        # Need minimum confidence
        if signal_score < MIN_CONFIDENCE:
            return None

        # Need at least 2 active signals
        if len(active) < 2:
            return None

        # ── Calculate levels ───────────────────────────────
        # Entry: current price (or slight pullback)
        entry = price

        # ATR for SL sizing
        atr_arr = talib.ATR(highs, lows, closes, 14)
        atr_c   = atr_arr[~np.isnan(atr_arr)]
        atr     = float(atr_c[-1]) if len(atr_c) else price * 0.02

        # SL: 2x ATR below entry (or below recent swing low)
        recent_low = lows[-8:].min()
        sl_atr     = entry - (atr * 2)
        sl         = max(sl_atr, recent_low * 0.995)

        sl_pct     = (sl - entry) / entry
        if abs(sl_pct) > 0.12:   # Cap SL at 12%
            sl = entry * 0.92
            sl_pct = -0.08

        # TP: minimum 2R, target recent resistance
        risk    = entry - sl
        tp_min  = entry + (risk * 2)
        recent_high = highs[-20:].max()

        if recent_high > tp_min:
            tp = recent_high * 0.995
        else:
            tp = tp_min

        tp_pct  = (tp - entry) / entry
        rr      = abs(tp_pct / sl_pct) if sl_pct != 0 else 0

        if rr < MIN_RR:
            return None

        # ── Build thesis ───────────────────────────────────
        thesis_parts = []

        if "MACD CROSS" in active:
            thesis_parts.append("MACD histogram just crossed positive")
        elif "MACD RISE" in active:
            thesis_parts.append("MACD momentum building for 3 consecutive candles")

        if "EMA STACK" in active:
            thesis_parts.append(
                f"price above EMA20 above EMA50 — clean bullish stack"
            )

        if "RSI MOMENTUM" in active:
            thesis_parts.append(
                f"RSI at {rsi_c[-1]:.0f} — momentum zone, not overbought"
            )

        if "VOL SURGE" in active:
            ratio = volumes[-1] / vol_avg
            thesis_parts.append(
                f"volume {ratio:.1f}x average — buyers stepping in"
            )

        if "HIGHER HIGHS" in active:
            thesis_parts.append("5 consecutive higher highs on this timeframe")

        if len(adx_c) and adx_c[-1] > 25:
            thesis_parts.append(f"ADX {adx_c[-1]:.0f} confirms active trend")

        thesis = ". ".join(thesis_parts).capitalize() + "."

        # ── Timestamps ────────────────────────────────────
        now        = int(time.time())
        expiry_secs = TRADE_EXPIRY_1D if timeframe == "1D" else TRADE_EXPIRY_4H

        coin_display = symbol.replace("USDT", "/USDT")

        return TradeIdea(
            coin       = coin_display,
            type       = "LONG",
            timeframe  = timeframe,
            entry      = format_price(entry, price),
            tp         = format_price(tp, price),
            sl         = format_price(sl, price),
            tp_pct     = f"+{tp_pct*100:.1f}",
            sl_pct     = f"{sl_pct*100:.1f}",
            rr         = f"{rr:.1f}",
            confidence = f"{int(signal_score * 100)}%",
            thesis     = thesis,
            signals    = signals[:6],
            active     = active[:4],
            posted     = "just now",
            expires    = time_remaining(now + expiry_secs),
            posted_ts  = now,
            expiry_ts  = now + expiry_secs,
            spark      = make_sparkline(closes),
        )


# ── Range Scanner ─────────────────────────────────────────────────────────────

class RangeScanner:
    """
    Finds sideways / consolidation setups suitable for range trading.
    Looks for: Low ADX, Bollinger Band squeeze, range-bound price action,
               multiple support/resistance touches.
    """

    def scan(self, symbol: str) -> TradeIdea | None:
        klines = get_klines(symbol, "4h", limit=100)
        if len(klines) < 50:
            return None
        return self._analyse(symbol, klines)

    def _analyse(self, symbol: str, klines: list) -> TradeIdea | None:

        closes  = np.array([k[4] for k in klines], dtype=float)
        highs   = np.array([k[2] for k in klines], dtype=float)
        lows    = np.array([k[3] for k in klines], dtype=float)
        volumes = np.array([k[5] for k in klines], dtype=float)

        price   = closes[-1]

        try:
            adx          = talib.ADX(highs, lows, closes, 14)
            bb_upper, bb_mid, bb_lower = talib.BBANDS(
                closes, timeperiod=20, nbdevup=2, nbdevdn=2
            )
            fastk, fastd = talib.STOCHRSI(
                closes, timeperiod=14,
                fastk_period=3, fastd_period=3, fastd_matype=0
            )
            rsi          = talib.RSI(closes, 14)
            atr          = talib.ATR(highs, lows, closes, 14)

            adx_c   = adx[~np.isnan(adx)]
            bbu_c   = bb_upper[~np.isnan(bb_upper)]
            bbm_c   = bb_mid[~np.isnan(bb_mid)]
            bbl_c   = bb_lower[~np.isnan(bb_lower)]
            rsi_c   = rsi[~np.isnan(rsi)]
            atr_c   = atr[~np.isnan(atr)]
            fk_c    = fastk[~np.isnan(fastk)]

            if len(adx_c) < 1 or len(bbu_c) < 1:
                return None

        except:
            return None

        # ── Signal checks ──────────────────────────────────
        signals      = []
        active       = []
        signal_score = 0

        # 1. Low ADX (no trend)
        current_adx = float(adx_c[-1])
        if current_adx < 20:
            signals.append(f"LOW ADX {current_adx:.0f}")
            active.append(f"LOW ADX {current_adx:.0f}")
            signal_score += 0.30
        elif current_adx < 25:
            signals.append(f"ADX {current_adx:.0f}")
            signal_score += 0.15

        # 2. BB squeeze (bands contracting)
        if len(bbu_c) >= 5 and len(bbl_c) >= 5:
            band_width_now  = float(bbu_c[-1] - bbl_c[-1]) / float(bbm_c[-1])
            band_width_5ago = float(bbu_c[-5] - bbl_c[-5]) / float(bbm_c[-5])
            if band_width_now < band_width_5ago * 0.85:
                signals.append("BB SQUEEZE")
                active.append("BB SQUEEZE")
                signal_score += 0.25

        # 3. Price within BB (not extended)
        if len(bbu_c) >= 1 and len(bbl_c) >= 1:
            bb_position = (price - float(bbl_c[-1])) / \
                          (float(bbu_c[-1]) - float(bbl_c[-1]) + 0.0001)
            if 0.2 <= bb_position <= 0.8:
                signals.append("IN RANGE")
                signal_score += 0.10

        # 4. StochRSI at range boundary
        if len(fk_c) >= 1:
            stoch_val = float(fk_c[-1])
            if stoch_val < 25:
                signals.append("STOCH LOW")
                active.append("STOCH LOW")
                signal_score += 0.20
            elif stoch_val > 75:
                signals.append("STOCH HIGH")
                active.append("STOCH HIGH")
                signal_score += 0.15

        # 5. Volume declining (consolidation)
        vol_avg_20 = np.mean(volumes[-21:-1])
        vol_avg_5  = np.mean(volumes[-6:-1])
        if vol_avg_20 > 0 and vol_avg_5 < vol_avg_20 * 0.75:
            signals.append("VOL DRY")
            active.append("VOL DRY")
            signal_score += 0.15

        # 6. Horizontal range check (price staying in range)
        recent_highs = highs[-16:]
        recent_lows  = lows[-16:]
        range_width  = (recent_highs.max() - recent_lows.min()) / price
        if range_width < 0.12:   # Less than 12% range over 16 candles
            signals.append("CONSOLIDATION")
            active.append("CONSOLIDATION")
            signal_score += 0.15

        if signal_score < MIN_CONFIDENCE:
            return None

        if len(active) < 2:
            return None

        # ── Calculate levels ───────────────────────────────
        # Range boundaries from recent price action
        range_high  = recent_highs.max()
        range_low   = recent_lows.min()
        range_mid   = (range_high + range_low) / 2

        atr_val     = float(atr_c[-1]) if len(atr_c) else price * 0.02

        # Entry at lower third of range (buying the dip)
        entry       = range_low + (range_high - range_low) * 0.25
        entry       = min(entry, price)   # Don't enter above current price

        # TP at upper range
        tp          = range_high * 0.99

        # SL below range
        sl          = range_low * 0.985

        sl_pct      = (sl - entry) / entry
        tp_pct      = (tp - entry) / entry

        if sl_pct == 0:
            return None

        rr          = abs(tp_pct / sl_pct)

        if rr < MIN_RR:
            return None

        # ── Thesis ────────────────────────────────────────
        thesis_parts = []

        if f"LOW ADX {current_adx:.0f}" in active:
            thesis_parts.append(
                f"ADX at {current_adx:.0f} — no trend, ideal range conditions"
            )

        if "BB SQUEEZE" in active:
            thesis_parts.append(
                "Bollinger Bands contracting — volatility compression"
            )

        if "CONSOLIDATION" in active:
            thesis_parts.append(
                f"price consolidating in {range_width*100:.1f}% range "
                f"over 16 candles"
            )

        if "STOCH LOW" in active:
            thesis_parts.append(
                "StochRSI at oversold extreme — historically bounces from here"
            )

        if "VOL DRY" in active:
            thesis_parts.append(
                "volume drying up — classic pre-breakout compression"
            )

        thesis = ". ".join(thesis_parts).capitalize() + "."

        now         = int(time.time())
        coin_display = symbol.replace("USDT", "/USDT")

        return TradeIdea(
            coin       = coin_display,
            type       = "RANGE",
            timeframe  = "4H",
            entry      = format_price(entry, price),
            tp         = format_price(tp, price),
            sl         = format_price(sl, price),
            tp_pct     = f"+{tp_pct*100:.1f}",
            sl_pct     = f"{sl_pct*100:.1f}",
            rr         = f"{rr:.1f}",
            confidence = f"{int(signal_score * 100)}%",
            thesis     = thesis,
            signals    = signals[:6],
            active     = active[:4],
            posted     = "just now",
            expires    = time_remaining(now + TRADE_EXPIRY_4H),
            posted_ts  = now,
            expiry_ts  = now + TRADE_EXPIRY_4H,
            spark      = make_sparkline(closes),
        )


# ── Main Scanner ──────────────────────────────────────────────────────────────

def run_scan() -> dict:
    """
    Run full scan across universe.
    Returns dict with trend and range trade ideas.
    """
    print(f"\n{'='*55}")
    print(f"CYPHER TRADE SPOTTER — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Scanning {len(UNIVERSE)} pairs...")
    print('='*55)

    trend_scanner = TrendScanner()
    range_scanner = RangeScanner()

    trend_ideas = []
    range_ideas = []

    for i, symbol in enumerate(UNIVERSE):
        print(f"  [{i+1:02d}/{len(UNIVERSE)}] {symbol:<15}", end="\r")

        # Trend scan
        if len(trend_ideas) < 3:
            try:
                idea = trend_scanner.scan(symbol)
                if idea:
                    trend_ideas.append(asdict(idea))
                    print(f"  ✅ TREND: {symbol} | "
                          f"RR:{idea.rr} | Conf:{idea.confidence}")
            except Exception as e:
                pass

        # Range scan
        if len(range_ideas) < 3:
            try:
                idea = range_scanner.scan(symbol)
                if idea:
                    range_ideas.append(asdict(idea))
                    print(f"  📊 RANGE: {symbol} | "
                          f"RR:{idea.rr} | Conf:{idea.confidence}")
            except Exception as e:
                pass

        # Stop once we have 3 of each
        if len(trend_ideas) >= 3 and len(range_ideas) >= 3:
            print(f"\n  Max ideas found — stopping early")
            break

        time.sleep(0.15)   # Rate limit

    print(f"\n{'='*55}")
    print(f"Scan complete:")
    print(f"  Trend ideas : {len(trend_ideas)}/3")
    print(f"  Range ideas : {len(range_ideas)}/3")

    results = {
        "scan_time":    datetime.now().isoformat(),
        "scan_time_ts": int(time.time()),
        "next_scan":    (
            datetime.now() + timedelta(seconds=SCAN_INTERVAL)
        ).strftime("%H:%M"),
        "trend_trades": trend_ideas,
        "range_trades": range_ideas,
    }

    return results


def write_output(results: dict):
    """Write results to JSON for dashboard to consume."""
    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Written to {OUTPUT_FILE}")


def main():
    parser = argparse.ArgumentParser(description="Cypher Trade Spotter")
    parser.add_argument("--watch",     action="store_true",
                        help="Continuous mode — rescan every 30 minutes")
    parser.add_argument("--dashboard", action="store_true",
                        help="Open dashboard after scan")
    parser.add_argument("--interval",  type=int, default=SCAN_INTERVAL,
                        help=f"Scan interval in seconds (default: {SCAN_INTERVAL})")
    args = parser.parse_args()

    if args.watch:
        print(f"Watch mode — scanning every {args.interval//60} minutes")
        while True:
            try:
                results = run_scan()
                write_output(results)
                print(f"\n  Next scan at {results['next_scan']}")
                print(f"  Sleeping {args.interval//60} minutes...")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\n  Stopped by operator")
                break
            except Exception as e:
                print(f"\n  Scan error: {e}")
                time.sleep(60)
    else:
        results = run_scan()
        write_output(results)

        if args.dashboard:
            import webbrowser
            webbrowser.open("cypher_spotter_dashboard.html")


if __name__ == "__main__":
    main()
