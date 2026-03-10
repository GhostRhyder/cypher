with open('/root/.openclaw/workspace/superpowers.py', 'r') as f:
    code = f.read()

# Replace calc_atr array access
code = code.replace(
"""    # Pionex kline format: [time, open, close, high, low, volume]
    closes = [float(k[2]) for k in klines]
    highs  = [float(k[3]) for k in klines]
    lows   = [float(k[4]) for k in klines]""",
"""    closes, highs, lows = [], [], []
    for k in klines:
        if isinstance(k, dict):
            closes.append(float(k.get('close', 0)))
            highs.append(float(k.get('high', 0)))
            lows.append(float(k.get('low', 0)))
        else:
            closes.append(float(k[2]))
            highs.append(float(k[3]))
            lows.append(float(k[4]))""")

# Replace calc_adx array access
code = code.replace(
"""    # Pionex kline format: [time, open, close, high, low, volume]
    closes = [float(k[2]) for k in klines]
    highs  = [float(k[3]) for k in klines]
    lows   = [float(k[4]) for k in klines]""",
"""    closes, highs, lows = [], [], []
    for k in klines:
        if isinstance(k, dict):
            closes.append(float(k.get('close', 0)))
            highs.append(float(k.get('high', 0)))
            lows.append(float(k.get('low', 0)))
        else:
            closes.append(float(k[2]))
            highs.append(float(k[3]))
            lows.append(float(k[4]))""")

with open('/root/.openclaw/workspace/superpowers.py', 'w') as f:
    f.write(code)

