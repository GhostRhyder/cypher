import os, hmac, hashlib, time, requests
from dotenv import load_dotenv

load_dotenv('/root/.openclaw/workspace/.env')
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

timestamp = int(time.time() * 1000)
query_string = f"timestamp={timestamp}"
signature = hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
url = f"https://api.binance.com/api/v3/account?{query_string}&signature={signature}"
headers = {"X-MBX-APIKEY": API_KEY}
print("URL:", url)
print("Headers:", headers)
response = requests.get(url, headers=headers)
print(response.status_code, response.text)
