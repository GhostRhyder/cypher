with open('new_dashboard_patched.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.strip() == '));' or line.strip() == '}':
        # Don't blindly remove `}`, only remove `));` and maybe check if we need to remove an extra `}`
        pass

# let's just use string replacement
with open('new_dashboard_patched.py', 'r') as f:
    content = f.read()

content = content.replace("                    });\n                }\n                ));\n                }", "                    });\n                }")
content = content.replace("                    data.logs_v3.forEach(l => combinedLogs.push({text: l, sys: 'PIONEX'}));\n                }\n                ));\n                }", "                    data.logs_v3.forEach(l => combinedLogs.push({text: l, sys: 'PIONEX'}));\n                }")

with open('new_dashboard_patched.py', 'w') as f:
    f.write(content)
