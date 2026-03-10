import urllib.request
import json
import time
import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()
user_key = os.getenv("PUSHOVER_USER_KEY")
api_token = os.getenv("PUSHOVER_API_TOKEN")

def send_push(message, title="CYPHER // ALERT"):
    url = "https://api.pushover.net/1/messages.json"
    data = urllib.parse.urlencode({
        "token": api_token,
        "user": user_key,
        "message": message,
        "title": title,
        "priority": 1 # High priority
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    try:
        urllib.request.urlopen(req)
    except Exception as e:
        print("Push failed:", e)

def check_jasmy():
    url = "https://api.binance.com/api/v3/klines?symbol=JASMYUSDT&interval=15m&limit=2"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        current_price = float(data[-1][4]) # Close price of current candle
        return current_price

print("Starting JASMY sniper daemon...")
while True:
    try:
        price = check_jasmy()
        print(f"Checking JASMY: {price}")
        
        # Condition 1: The Dip Buy (Support retest)
        if price <= 0.005850:
            msg = f"Target Acquired: JASMY has dropped to {price:.6f}. The dip has arrived. Prepare for LONG entry evaluation."
            send_push(msg, "CYPHER // DIP ALERT")
            print("Alert sent (Dip). Exiting.")
            break
            
        # Condition 2: The Breakout (Continuation)
        elif price >= 0.006050:
            msg = f"Target Acquired: JASMY is breaking local resistance at {price:.6f}. Upward momentum is resuming. Prepare for LONG breakout."
            send_push(msg, "CYPHER // BREAKOUT ALERT")
            print("Alert sent (Breakout). Exiting.")
            break
            
        time.sleep(60) # Check every 60 seconds
    except Exception as e:
        print("Error fetching data:", e)
        time.sleep(60)
