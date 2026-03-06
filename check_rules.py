from pionex_api_template import send_pionex_request

def check_symbol_rules(symbol):
    # Endpoint: /api/v1/common/symbols (or similar)
    # Pionex V1 endpoint for symbols info
    print(f"Checking rules for {symbol}...")
    try:
        data = send_pionex_request("GET", "/api/v1/common/symbols")
        if not data or 'data' not in data or 'symbols' not in data['data']:
             print("⚠️  No symbol info found.")
             return
             
        symbols = data['data']['symbols']
        # Find our symbol
        rule = next((s for s in symbols if s['symbol'] == symbol), None)
        
        if rule:
            print(f"✅ Rules for {symbol}:")
            print(f"   Base Precision: {rule.get('basePrecision')}")
            print(f"   Quote Precision: {rule.get('quotePrecision')}")
            print(f"   Min Amount: {rule.get('minAmount')}")
            print(f"   Min Trade Size: {rule.get('minTradeSize')}")
        else:
            print(f"❌ Symbol {symbol} not found in rules.")
            
    except Exception as e:
        print(f"⚠️ Error: {e}")

if __name__ == "__main__":
    check_symbol_rules("BTC_USDT")
