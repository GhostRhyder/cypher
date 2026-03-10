import re
import json

with open("trade_daemon_v2.py", "r") as f:
    code = f.read()

import_block = """import talib
import json
import os
import time
from datetime import datetime
import threading
from pionex_api_template import send_pionex_request
from superpowers import get_trade_params
"""

if "from superpowers import get_trade_params" not in code:
    code = code.replace("import talib\nimport json\nimport os\nimport time\nfrom datetime import datetime\nimport threading\nfrom pionex_api_template import send_pionex_request", import_block)

# Let's find the entry logic inside run_bot
entry_block_pattern = re.compile(r'if spread <= MAX_SPREAD:.*?(if len\(state\[\'positions\'\]\) < MAX_POSITIONS:)', re.DOTALL)
# Actually, let's inject it where it decides to buy a new coin.

with open("trade_daemon_v2.py", "w") as f:
    f.write(code)
print("Import patched.")
