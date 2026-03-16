import pandas as pd
import numpy as np

class Backtester:
    def __init__(self, df):
        self.df = df
        self.prepare_indicators()

    def prepare_indicators(self):
        """Precompute indicators used in the daemon's entry logic (without TA-Lib)."""
        close = self.df['close']
        
        # 1. RSI calculation
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        self.df['rsi'] = 100 - (100 / (1 + rs))
        
        # 2. StochRSI calculation
        min_rsi = self.df['rsi'].rolling(window=14).min()
        max_rsi = self.df['rsi'].rolling(window=14).max()
        stoch_rsi = (self.df['rsi'] - min_rsi) / (max_rsi - min_rsi)
        self.df['fastk'] = stoch_rsi.rolling(window=3).mean() * 100
        self.df['fastd'] = self.df['fastk'].rolling(window=3).mean()
        
        # 3. MACD calculation
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        self.df['macd'] = exp1 - exp2
        self.df['macd_signal'] = self.df['macd'].ewm(span=9, adjust=False).mean()

    def check_entry_signals(self, i):
        """Check for entry signals at index i based on the daemon script."""
        if i < 2: return None
        
        # S5_Scalp — StochRSI cross up from oversold
        fastk = self.df['fastk'].iloc[i]
        fastd = self.df['fastd'].iloc[i]
        fastk_prev = self.df['fastk'].iloc[i-1]
        fastd_prev = self.df['fastd'].iloc[i-1]
        
        if not np.isnan(fastk) and not np.isnan(fastd):
            if fastk < 20 and fastk > fastd and fastk_prev <= fastd_prev:
                return "S5_Scalp"
            
        # S4_Momentum — MACD cross with RSI > 50
        macd = self.df['macd'].iloc[i]
        macd_signal = self.df['macd_signal'].iloc[i]
        rsi = self.df['rsi'].iloc[i]
        macd_prev = self.df['macd'].iloc[i-1]
        macd_signal_prev = self.df['macd_signal'].iloc[i-1]
        
        if not np.isnan(macd) and not np.isnan(macd_signal) and not np.isnan(rsi):
            if macd > macd_signal and rsi > 50 and macd_prev <= macd_signal_prev:
                return "S4_Momentum"
            
        return None

    def run_backtest(self, tp_pct, sl_pct, trail=False, trail_act=0, trail_dist=0, kill_time=None):
        """Run a single backtest with given TP/SL and other parameters."""
        trades = []
        active_trade = None
        
        for i in range(1, len(self.df)):
            if active_trade is None:
                signal = self.check_entry_signals(i)
                if signal:
                    active_trade = {
                        'entry_price': self.df['close'].iloc[i],
                        'entry_time': self.df['timestamp'].iloc[i],
                        'peak': self.df['close'].iloc[i],
                        'signal': signal,
                        'entry_index': i
                    }
            else:
                current_price = self.df['close'].iloc[i]
                high_price = self.df['high'].iloc[i]
                low_price = self.df['low'].iloc[i]
                
                if high_price > active_trade['peak']:
                    active_trade['peak'] = high_price
                
                profit_pct_low = (low_price - active_trade['entry_price']) / active_trade['entry_price']
                profit_pct_high = (high_price - active_trade['entry_price']) / active_trade['entry_price']
                
                exit_price = None
                exit_reason = None
                
                if profit_pct_low <= -sl_pct:
                    exit_price = active_trade['entry_price'] * (1 - sl_pct)
                    exit_reason = "SL"
                elif not trail and profit_pct_high >= tp_pct:
                    exit_price = active_trade['entry_price'] * (1 + tp_pct)
                    exit_reason = "TP"
                elif trail and active_trade['peak'] >= active_trade['entry_price'] * (1 + trail_act):
                    if low_price <= active_trade['peak'] * (1 - trail_dist):
                        exit_price = active_trade['peak'] * (1 - trail_dist)
                        exit_reason = "TRAIL"
                elif kill_time and (i - active_trade['entry_index']) >= kill_time:
                    exit_price = current_price
                    exit_reason = "KILL_TIME"
                
                if exit_price:
                    pnl_pct = (exit_price - active_trade['entry_price']) / active_trade['entry_price'] * 100
                    trades.append({
                        'entry': active_trade['entry_price'],
                        'exit': exit_price,
                        'pnl_pct': pnl_pct,
                        'signal': active_trade['signal'],
                        'entry_time': str(active_trade['entry_time']),
                        'exit_time': str(self.df['timestamp'].iloc[i]),
                        'reason': exit_reason
                    })
                    active_trade = None
        
        return trades

    def optimize(self, tp_range, sl_range, step=0.001):
        """Run optimization over a range of TP and SL values."""
        results = []
        for tp in np.arange(tp_range[0], tp_range[1] + step, step):
            for sl in np.arange(sl_range[0], sl_range[1] + step, step):
                trades = self.run_backtest(tp, sl)
                if not trades:
                    results.append({'tp': round(tp, 4), 'sl': round(sl, 4), 'total_pnl': 0, 'win_rate': 0, 'trade_count': 0})
                    continue
                
                pnl_list = [t['pnl_pct'] for t in trades]
                total_pnl = sum(pnl_list)
                wins = len([p for p in pnl_list if p > 0])
                win_rate = wins / len(pnl_list) * 100
                
                results.append({
                    'tp': round(tp, 4),
                    'sl': round(sl, 4),
                    'total_pnl': round(total_pnl, 2),
                    'win_rate': round(win_rate, 2),
                    'trade_count': len(trades)
                })
        
        return sorted(results, key=lambda x: x['total_pnl'], reverse=True)
