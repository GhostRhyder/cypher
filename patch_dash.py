import re

with open('new_dashboard_patched.py', 'r') as f:
    code = f.read()

# Remove the left column HTML
code = re.sub(r'<!-- LEFT COLUMN: BINANCE \(SWING\) -->.*?</div>\s*<!-- RIGHT COLUMN: PIONEX \(SCALPER\) -->', '<!-- RIGHT COLUMN: PIONEX (SCALPER) -->', code, flags=re.DOTALL)

# Change grid to 1 column or just remove grid
code = code.replace('.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }', '.grid { display: block; margin-bottom: 20px; }')

# In renderLiveTrades call
code = code.replace("renderLiveTrades('trade-data-binance', data.state_swing, 'BINANCE');", "")

# In the filter history options
code = re.sub(r'<option value="BINANCE">Binance Only</option>', '', code)
code = re.sub(r'<option value="BINANCE">Binance Only</option>', '', code) # log filter

# In the history parsing
code = re.sub(r'if \(filterHist === \'ALL\' \|\| filterHist === \'BINANCE\'\) \{.*?\}', '', code, flags=re.DOTALL)

# In the log parsing
code = re.sub(r'if \(logFilter === \'ALL\' \|\| logFilter === \'BINANCE\'\) \{.*?\}', '', code, flags=re.DOTALL)

with open('new_dashboard_patched.py', 'w') as f:
    f.write(code)

