import json
import time
from trade_daemon_v2 import execute_sell, save_trade_history, get_ticker

with open("state.json", "r") as f:
    state = json.load(f)

nft_pos = next((p for p in state.get('positions', []) if p['coin'] == 'NFT_USDT'), None)
if nft_pos:
    print("Force closing NFT_USDT...")
    current_price = get_ticker("NFT_USDT")
    if current_price and execute_sell("NFT_USDT"):
        print("Sold successfully.")
        pnl_pct = (current_price - nft_pos['entry_price']) / nft_pos['entry_price'] * 100
        save_trade_history("NFT_USDT", nft_pos['entry_price'], current_price, pnl_pct, nft_pos.get('cost_basis', 20.50), nft_pos.get('start_time'))
        
        state['positions'] = [p for p in state['positions'] if p['coin'] != 'NFT_USDT']
        with open("state.json", "w") as f:
            json.dump(state, f)
        print("State updated.")
    else:
        print("Failed to sell.")
else:
    print("NFT not found in state.")
