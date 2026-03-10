with open("dashboard.py", "r") as f:
    content = f.read()

import re

# Find the start of the card div for history
# `<div class="card" style="margin-bottom: 20px;">`
# up to `<table id="history-table">`

pattern = re.compile(r'<div class="card" style="margin-bottom: 20px;">.*?<table id="history-table">', re.DOTALL)

new_html = """<div class="card" style="margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 1px solid #30363d; margin-bottom: 15px;">
                <div style="display: flex; flex-direction: column; gap: 10px;">
                    <h3 id="history-title" style="margin: 0; border: none; padding: 0;">TRADE HISTORY</h3>
                    <div style="display: flex; gap: 5px;">
                        <button id="tab-v3" class="tab-btn active" onclick="setTab('V3')">V3 Trades</button>
                        <button id="tab-v2" class="tab-btn" onclick="setTab('V2')">V2 Trades</button>
                    </div>
                </div>
                <div style="display: flex; flex-direction: column; gap: 10px; align-items: flex-end; padding-bottom: 5px;">
                    <div id="total-pnl" style="font-weight: bold; font-size: 16px;">Total PnL: Calculating...</div>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <button onclick="changePage(-1)" id="btn-prev" style="background: #238636; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer;">Prev</button>
                        <span id="page-info">Page 1</span>
                        <button onclick="changePage(1)" id="btn-next" style="background: #238636; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer;">Next</button>
                    </div>
                </div>
            </div>
            <table id="history-table">"""

if pattern.search(content):
    content = pattern.sub(new_html, content)
    with open("dashboard.py", "w") as f:
        f.write(content)
    print("Fixed HTML layout.")
else:
    print("Pattern not found!")

