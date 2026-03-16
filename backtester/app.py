from flask import Flask, render_template, request, jsonify
from data_manager import DataManager
from backtester import Backtester
import os

# Set template folder to current directory for index.html
app = Flask(__name__, template_folder='.')

dm = DataManager()

@app.route('/')
def index():
    # Render index.html from the current directory
    return render_template('index.html')

@app.route('/api/top_coins')
def get_top_coins():
    coins = dm.get_top_volume_coins()
    return jsonify(coins)

@app.route('/api/backtest', methods=['POST'])
def run_backtest():
    data = request.json
    symbol = data.get('symbol', 'BTCUSDT')
    tp = float(data.get('tp', 0.008))
    sl = float(data.get('sl', 0.005))
    trail = data.get('trail', False)
    trail_act = float(data.get('trail_act', 0.01))
    trail_dist = float(data.get('trail_dist', 0.005))
    kill_time = data.get('kill_time')
    if kill_time is not None:
        kill_time = int(kill_time)
    
    df = dm.fetch_candles(symbol)
    if df is None:
        return jsonify({"error": "Failed to fetch data"}), 400
        
    bt = Backtester(df)
    trades = bt.run_backtest(tp, sl, trail, trail_act, trail_dist, kill_time)
    
    return jsonify(trades)

@app.route('/api/optimize', methods=['POST'])
def run_optimization():
    data = request.json
    symbol = data.get('symbol', 'BTCUSDT')
    tp_min = float(data.get('tp_min', 0.005))
    tp_max = float(data.get('tp_max', 0.015))
    sl_min = float(data.get('sl_min', 0.003))
    sl_max = float(data.get('sl_max', 0.01))
    step = float(data.get('step', 0.001))
    signal_type = data.get('signal_type') # New field: 'S4_Momentum' or 'S5_Scalp'
    
    df = dm.fetch_candles(symbol)
    if df is None:
        return jsonify({"error": "Failed to fetch data"}), 400
        
    bt = Backtester(df)
    results = bt.optimize((tp_min, tp_max), (sl_min, sl_max), step, signal_type=signal_type)
    
    return jsonify(results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
