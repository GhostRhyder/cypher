with open('new_dashboard_patched.py', 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.startswith('state_v3 = read_json_safe("state.json"'):
        lines[i] = '            ' + line

with open('new_dashboard_patched.py', 'w') as f:
    f.writelines(lines)
