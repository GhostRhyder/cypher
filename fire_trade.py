import time
from pionex_api_template import place_market_buy

COINS = ["SOL_USDT", "ADA_USDT"]
AMOUNT = 12.0

def execute_orders():
    print(f"🔥 FIRE MISSION: {len(COINS)} Targets @ ${AMOUNT} each.")
    
    for symbol in COINS:
        print(f"\n🚀 Engaging {symbol}...")
        resp = place_market_buy(symbol, AMOUNT)
        
        if resp and resp.get('result', False):
            print(f"✅ ORDER FILLED: {symbol} | ID: {resp.get('data', {}).get('orderId', 'Unknown')}")
        else:
            print(f"❌ ORDER FAILED: {symbol} | Reason: {resp}")
            
        time.sleep(1) # Rate limit safety

if __name__ == "__main__":
    print("Auto-confirming launch... 🚀")
    execute_orders()
