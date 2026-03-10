import json

with open("history.json", "r") as f:
    history = json.load(f)

if history[-1]["coin"] == "NFT_USDT" and history[-1]["version"] == "V3":
    history[-1]["version"] = "V2"
    with open("history.json", "w") as f:
        json.dump(history, f, indent=2)
    print("Fixed NFT version to V2.")
else:
    print("Not found or already fixed.")
