import os
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime
from pionex_api_template import send_pionex_request

# --- SETUP ---
load_dotenv()

# --- FUNCTIONS ---

def get_top_10_volume():
    """Fetches Top 10 coins by 24h Volume on Pionex."""
    print("🔍 Scanning Top 10 by Volume...")
    try:
        # Endpoint: /api/v1/market/tickers
        data = send_pionex_request("GET", "/api/v1/market/tickers")
        
        if not data or 'data' not in data or 'tickers' not in data['data']:
            print(f"⚠️ API Error (Tickers): {data}")
            return []
            
        tickers = data['data']['tickers']
        # Convert to DataFrame
        df = pd.DataFrame(tickers)
        
        # Filter for USDT pairs
        df = df[df['symbol'].str.endswith('_USDT')]
        
        # Convert to numeric
        df['amount'] = pd.to_numeric(df['amount'])
        
        # Sort by quote volume (amount)
        top_10 = df.sort_values(by='amount', ascending=False).head(10)
        
        print("\n🏆 Top 10 Coins (24h Volume):")
        for i, row in top_10.iterrows():
            vol_m = row['amount'] / 1_000_000
            print(f"{i+1}. {row['symbol']} (${vol_m:.2f}M)")
        
        return top_10['symbol'].tolist()
    except Exception as e:
        print(f"⚠️ Error processing volume: {e}")
        return []

def check_balance():
    """Checks USDT balance."""
    print("💰 Checking Balance...")
    try:
        # Endpoint: /api/v1/account/balances
        data = send_pionex_request("GET", "/api/v1/account/balances")
        
        if not data or 'data' not in data or 'balances' not in data['data']:
            print(f"⚠️ API Error (Balance): {data}")
            return 0
            
        balances = data['data']['balances']
        # Find USDT
        usdt_bal = next((item for item in balances if item['coin'] == 'USDT'), None)
        
        if usdt_bal:
            free = float(usdt_bal['free'])
            frozen = float(usdt_bal['frozen'])
            total = free + frozen
            print(f"\n💵 Wallet: ${free:.2f} Free / ${total:.2f} Total")
            return free
        else:
            print("⚠️ USDT balance not found.")
            return 0
            
    except Exception as e:
        print(f"⚠️ Error checking balance: {e}")
        return 0

# --- MAIN LOOP ---

def main():
    print(f"🤖 Pionex Agent Online (Template Powered) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 40)
    
    # 1. Check Connection & Balance
    free_usdt = check_balance()
    
    # 2. Risk Check
    if free_usdt < 10:
        print("⚠️ WARNING: Balance below $10 minimum trade size.")
    
    # 3. Scan Universe
    universe = get_top_10_volume()
    
    print("-" * 40)
    print(f"✅ READY. Monitoring {len(universe)} pairs.")
    print("waiting for alerts...")

if __name__ == "__main__":
    main()
