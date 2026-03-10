import re

with open('/root/.openclaw/workspace/new_dashboard_patched.py', 'r') as f:
    content = f.read()

old_str = "document.getElementById('total-pnl').innerHTML = `Total PnL: <span style=\"color: ${totalColor};\">${totalSign}$${runningTotal.toFixed(2)}</span>`;"
new_str = "document.getElementById('total-pnl').innerHTML = `Total ${allHistory.length} PnL: <span style=\"color: ${totalColor};\">${totalSign}$${runningTotal.toFixed(2)}</span>`;"

content = content.replace(old_str, new_str)

with open('/root/.openclaw/workspace/new_dashboard_patched.py', 'w') as f:
    f.write(content)
