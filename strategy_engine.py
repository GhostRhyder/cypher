import pandas as pd
import numpy as np
import talib
from datetime import datetime
from main import get_top_10_volume # Reuse logic
from pionex_api_template import get_candles

# --- CONFIG ---
STRATEGIES = {
    "S1_Trend": "EMA20 > EMA50 (Trend Following)",
    "S2_Reversion": "Price < LowerBB + RSI < 30 (Dip Buy)",
    "S3_Squeeze": "BB Width Low + Price > UpperBB (Breakout)",
    "S4_Momentum": "MACD > Signal + RSI > 50 (Strong Move)",
    "S5_Scalp": "StochRSI Cross Up < 20 (Quick Bounce)"
}

TIMEFRAMES = ["5M", "15M", "60M"] # Added 5M for Scalping

def analyze_candles(symbol, timeframe):
    """
    Fetches candles and runs TA-Lib indicators.
    Returns a dict of signals { "S1": True/False, ... }
    """
    # 1. Fetch Data
    resp = get_candles(symbol, timeframe, limit=100)
    if not resp:
        print(f"⚠️ Warning: No response for {symbol}")
        return {}
    if 'data' not in resp or 'klines' not in resp['data']:
        print(f"⚠️ Warning: Bad response structure for {symbol}: {resp}")
        return {}

    # Parse Klines: [time, open, close, high, low, vol]
    # Pionex returns: [time, open, close, high, low, vol] ? Let's verify.
    # Usually: [time, open, close, high, low, volume]
    
    # Debug structure if needed. Assuming standard OHLCV list of lists.
    klines = resp['data']['klines']
    if not klines:
        print(f"⚠️ Warning: Empty klines for {symbol}")
        return {}
        
    df = pd.DataFrame(klines, columns=['time', 'open', 'close', 'high', 'low', 'volume'])
    df['close'] = pd.to_numeric(df['close']).astype(float)
    df['high'] = pd.to_numeric(df['high']).astype(float)
    df['low'] = pd.to_numeric(df['low']).astype(float)
    df['volume'] = pd.to_numeric(df['volume']).astype(float)
    
    # 2. Compute Indicators (TA-Lib)
    print(f"DEBUG: {symbol} [{timeframe}] - {len(df)} candles")
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    
    # EMA
    ema20 = talib.EMA(close, timeperiod=20)
    ema50 = talib.EMA(close, timeperiod=50)
    
    # Bollinger Bands
    upper, middle, lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
    bb_width = (upper - lower) / middle
    
    # RSI
    rsi = talib.RSI(close, timeperiod=14)
    
    # MACD
    macd, macd_signal, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    
    # Stochastic RSI
    # TA-Lib StochRSI returns fastk, fastd
    fastk, fastd = talib.STOCHRSI(close, timeperiod=14, fastk_period=3, fastd_period=3, fastd_matype=0)
    
    # 3. Check Signals (on the LATEST completed candle i.e. index -1)
    # Using index -1 is current candle (incomplete). Use -2 for confirmed close?
    # Let's use -1 for real-time alerts, but be aware it can repaint.
    idx = -1 
    
    signals = {}
    
    # S1: Trend Hunter (EMA Cross)
    # Condition: EMA20 > EMA50
    if ema20[idx] > ema50[idx]:
        signals["S1_Trend"] = True
    
    # S2: Rubber Band (Mean Reversion)
    # Condition: Close < LowerBB AND RSI < 30
    if close[idx] < lower[idx] and rsi[idx] < 30:
        signals["S2_Reversion"] = True
        
    # S3: The Squeeze (Breakout)
    # Condition: BB Width < 0.05 (Tight) AND Close > UpperBB
    # (Threshold 0.05 is arbitrary, tune later)
    if bb_width[idx] < 0.10 and close[idx] > upper[idx]:
         signals["S3_Squeeze"] = True
         
    # S4: The Rocket (Momentum)
    # Condition: MACD > Signal AND RSI > 50
    if macd[idx] > macd_signal[idx] and rsi[idx] > 50:
        signals["S4_Momentum"] = True
        
    # S5: The Sniper (Scalp)
    # Condition: StochRSI K crosses D upwards from < 20
    # Logic: K > D now, but K < D previous candle? Or just K < 20 and K > D?
    if fastk[idx] < 20 and fastk[idx] > fastd[idx]:
        signals["S5_Scalp"] = True
        
    return signals

def run_strategy_scan():
    print(f"\n🚀 Starting Strategy Scan - {datetime.now().strftime('%H:%M:%S')}")
    
    # 1. Get Universe
    top_10 = get_top_10_volume() # From main.py
    
    results = []
    
    print(f"\nScanning {len(top_10)} coins across {len(TIMEFRAMES)} timeframes...")
    
    for symbol in top_10:
        # print(f"  Analyzing {symbol}...")
        for tf in TIMEFRAMES:
            signals = analyze_candles(symbol, tf)
            
            # Log any active signal
            for strat, active in signals.items():
                if active:
                    res = {
                        "Symbol": symbol,
                        "Timeframe": tf,
                        "Strategy": strat,
                        "Desc": STRATEGIES[strat]
                    }
                    results.append(res)
                    print(f"    🔥 SIGNAL: {symbol} [{tf}] - {strat}")

    # 2. Output Report
    if not results:
        print("\n😴 No signals detected right now.")
    else:
        print(f"\n✅ Scan Complete. Found {len(results)} active signals.")
        # Save to file?
        df_res = pd.DataFrame(results)
        print(df_res)
        
        # Append to signals_log.md
        with open("signals_log.md", "a") as f:
            f.write(f"\n### Scan: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(df_res.to_markdown(index=False))
            f.write("\n")

if __name__ == "__main__":
    run_strategy_scan()
