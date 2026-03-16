with open('new_dashboard_patched.py', 'r') as f:
    code = f.read()

# Replace the specific syntax errors
code = code.replace("                    });\n                }\n                }\n                \n                allHistory.sort", "                    });\n                }\n                \n                allHistory.sort")

code = code.replace("                    data.logs_v3.forEach(l => combinedLogs.push({text: l, sys: 'PIONEX'}));\n                }\n                }\n                \n                combinedLogs.sort", "                    data.logs_v3.forEach(l => combinedLogs.push({text: l, sys: 'PIONEX'}));\n                }\n                \n                combinedLogs.sort")

with open('new_dashboard_patched.py', 'w') as f:
    f.write(code)
