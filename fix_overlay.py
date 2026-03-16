with open('new_dashboard_patched.py', 'r') as f:
    code = f.read()

# Fix rescan() logic to use 'hidden' class
code = code.replace("overlay.classList.add('active');", "overlay.classList.remove('hidden');")
code = code.replace("overlay.classList.remove('active');", "overlay.classList.add('hidden');")

# Add window.onload logic to hide overlay on initial load
init_logic = """
        window.addEventListener('load', () => {
            setTimeout(() => {
                document.getElementById('scanOverlay').classList.add('hidden');
            }, 1000);
        });
        
        setInterval(updateDashboard, 3000);
"""
# Replace the old setInterval call
code = code.replace("setInterval(updateDashboard, 3000);", init_logic)

# Make sure .hidden class is definitely in the CSS if it's not
if ".hidden {" not in code:
    code = code.replace("</style>", "  .hidden { display: none !important; }\n    </style>")

with open('new_dashboard_patched.py', 'w') as f:
    f.write(code)

