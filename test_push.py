import urllib.request
import urllib.parse
import json

def send_push(user_key, api_token, message, title="Cypher"):
    url = "https://api.pushover.net/1/messages.json"
    data = urllib.parse.urlencode({
        "token": api_token,
        "user": user_key,
        "message": message,
        "title": title
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        return {"status": 0, "error": str(e)}

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    user_key = os.getenv("PUSHOVER_USER_KEY")
    api_token = os.getenv("PUSHOVER_API_TOKEN")
    
    res = send_push(user_key, api_token, "Connection established. Awaiting target coordinates. 🕸️", title="CYPHER // UPLINK")
    print(res)
