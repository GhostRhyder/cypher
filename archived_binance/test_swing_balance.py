import sys
sys.path.append("/root/.openclaw/workspace")
from pionex_api_swing import send_pionex_request

res = send_pionex_request("GET", "/api/v1/account/balances")
if res and res.get("result"):
    for b in res["data"]["balances"]:
        if b["coin"] == "USDT":
            print("USDT Balance:", b)
else:
    print("Error fetching balance:", res)
