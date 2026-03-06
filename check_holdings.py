from pionex_api_template import send_pionex_request

def check_all_balances():
    print("💰 Checking Full Portfolio...")
    try:
        data = send_pionex_request("GET", "/api/v1/account/balances")
        
        if not data or 'data' not in data or 'balances' not in data['data']:
            print(f"⚠️ API Error: {data}")
            return
            
        balances = data['data']['balances']
        
        print("\n--- Non-Zero Balances ---")
        for item in balances:
            free = float(item['free'])
            frozen = float(item['frozen'])
            total = free + frozen
            
            if total > 0:
                print(f"🪙 {item['coin']}: {free:.6f} Free | {frozen:.6f} Frozen | Total: {total:.6f}")
                
    except Exception as e:
        print(f"⚠️ Error: {e}")

if __name__ == "__main__":
    check_all_balances()
