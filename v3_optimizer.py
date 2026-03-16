import argparse
import pandas as pd
import numpy as np
import requests
import talib

def fetch_binance_data(symbol, interval="5m", limit=1000):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    res = requests.get(url)
    data = res.json()
    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'qav', 'num_trades', 'tbbav', 'tbqav', 'ignore'
    ])
    cols = ['open', 'high', 'low', 'close', 'volume']
    df[cols] = df[cols].apply(pd.to_numeric)
    return df

def calculate_indicators(df):
    close = df['close'].values
    
    # S5_Scalp StochRSI
    fastk, fastd = talib.STOCHRSI(close, timeperiod=14, fastk_period=3, fastd_period=3, fastd_matype=0)
    df['fastk'] = fastk
    df['fastd'] = fastd
    
    # S4_Momentum MACD & RSI
    macd, macd_signal, _ = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    rsi = talib.RSI(close, timeperiod=14)
    df['macd'] = macd
    df['macd_signal'] = macd_signal
    df['rsi'] = rsi
    
    return df

def run_backtest(df, tp_pct, sl_pct, trail_dist=0.0, kill_time=0):
    trades = []
    in_trade = False
    entry_price = 0
    peak_price = 0
    entry_idx = 0
    
    for i in range(2, len(df)):
        if not in_trade:
            # S5_Scalp & S4_Momentum
            s5 = (df['fastk'].iloc[i] < 20 and df['fastk'].iloc[i] > df['fastd'].iloc[i] and df['fastk'].iloc[i-1] <= df['fastd'].iloc[i-1])
            s4 = (df['macd'].iloc[i] > df['macd_signal'].iloc[i] and df['rsi'].iloc[i] > 50 and df['macd'].iloc[i-1] <= df['macd_signal'].iloc[i-1])
            
            if s5 or s4:
                in_trade = True
                entry_price = df['close'].iloc[i]
                peak_price = entry_price
                entry_idx = i
        else:
            high = df['high'].iloc[i]
            low = df['low'].iloc[i]
            close = df['close'].iloc[i]
            
            if high > peak_price:
                peak_price = high
                
            p_low = (low - entry_price) / entry_price
            p_high = (high - entry_price) / entry_price
            
            exit_p = None
            if p_low <= -sl_pct:
                exit_p = entry_price * (1 - sl_pct)
            elif trail_dist > 0 and peak_price >= entry_price * (1 + tp_pct):
                if low <= peak_price * (1 - trail_dist):
                    exit_p = peak_price * (1 - trail_dist)
            elif trail_dist == 0 and p_high >= tp_pct:
                exit_p = entry_price * (1 + tp_pct)
            elif kill_time > 0 and (i - entry_idx) >= kill_time:
                exit_p = close
                
            if exit_p:
                trades.append((exit_p - entry_price) / entry_price * 100)
                in_trade = False
                
    # Close open trade at end
    if in_trade:
        exit_p = df['close'].iloc[-1]
        trades.append((exit_p - entry_price) / entry_price * 100)
        
    pnl = sum(trades)
    wr = (sum(1 for t in trades if t > 0) / len(trades) * 100) if trades else 0
    return pnl, wr, len(trades)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', default='BTCUSDT')
    parser.add_argument('--limit', type=int, default=1000)
    parser.add_argument('--tp_min', type=float, default=0.005)
    parser.add_argument('--tp_max', type=float, default=0.02)
    parser.add_argument('--tp_step', type=float, default=0.001)
    parser.add_argument('--sl_min', type=float, default=0.003)
    parser.add_argument('--sl_max', type=float, default=0.015)
    parser.add_argument('--sl_step', type=float, default=0.001)
    parser.add_argument('--trail_dist', type=float, default=0.0, help="Trailing stop distance % (0 = disabled)")
    parser.add_argument('--kill_time', type=int, default=0, help="Max 5m candles to hold (0 = disabled)")
    args = parser.parse_args()
    
    print(f"Fetching {args.limit} candles for {args.symbol} (5M)...")
    df = fetch_binance_data(args.symbol, limit=args.limit)
    df = calculate_indicators(df)
    
    tp_range = np.arange(args.tp_min, args.tp_max + args.tp_step/2, args.tp_step)
    sl_range = np.arange(args.sl_min, args.sl_max + args.sl_step/2, args.sl_step)
    
    print(f"Optimizing over {len(tp_range)} TP steps and {len(sl_range)} SL steps...")
    if args.trail_dist > 0: print(f"Using Trailing Stop: {args.trail_dist*100:.1f}%")
    if args.kill_time > 0: print(f"Using Kill Time: {args.kill_time} candles ({args.kill_time*5} mins)")
    
    results = []
    for tp in tp_range:
        for sl in sl_range:
            pnl, wr, count = run_backtest(df, tp, sl, args.trail_dist, args.kill_time)
            if count > 0:
                results.append((tp, sl, pnl, wr, count))
                
    results.sort(key=lambda x: x[2], reverse=True)
    
    print("\n--- Top 10 Optimization Results ---")
    print("TP %   | SL %   | Total PnL | Win Rate | Trades")
    print("-" * 50)
    for r in results[:10]:
        print(f"{r[0]*100:5.1f}% | {r[1]*100:5.1f}% | {r[2]:8.2f}% | {r[3]:7.1f}% | {r[4]:5}")

if __name__ == "__main__":
    main()
