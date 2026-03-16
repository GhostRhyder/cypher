import json
import os

with open('new_dashboard_patched.py', 'r') as f:
    code = f.read()

# Add read_json_safe for trades.json
api_data_pos = code.find('state_v3 = read_json_safe("state.json", {"state": "OFFLINE"})')
if api_data_pos != -1:
    insertion = '            spotter_data = read_json_safe("trades.json", {"trend_trades": [], "range_trades": [], "scan_time": ""})\n'
    code = code[:api_data_pos] + insertion + code[api_data_pos:]
    
    dict_pos = code.find('"logs_swing": logs_swing')
    if dict_pos != -1:
        code = code[:dict_pos] + '"logs_swing": logs_swing,\n                "spotter_data": spotter_data\n            ' + code[dict_pos + len('"logs_swing": logs_swing'):]

with open('new_dashboard_patched.py', 'w') as f:
    f.write(code)
