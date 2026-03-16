with open('new_dashboard_patched.py', 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "spotter_data = read_json_safe(\"trades.json\"" in line:
        lines[i] = '            spotter_data = read_json_safe("trades.json", {"trend_trades": [], "range_trades": [], "scan_time": ""})\n'

with open('new_dashboard_patched.py', 'w') as f:
    f.writelines(lines)
