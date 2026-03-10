import json
from datetime import datetime

trade_log = {
    "timestamp": datetime.now().isoformat(),
    "asset": "JASMY/USDT",
    "type": "LONG",
    "entry": 0.005802,
    "stop_loss": 0.005697,
    "margin": 88.36,
    "leverage": 10,
    "status": "OPEN (Free Runner Protocol active)"
}
try:
    with open("war_room_log.json", "r") as f:
        logs = json.load(f)
except:
    logs = []

logs.append(trade_log)

with open("war_room_log.json", "w") as f:
    json.dump(logs, f, indent=2)

print("War Room trade logged.")
