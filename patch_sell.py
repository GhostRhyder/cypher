import re

with open("trade_daemon_v2.py", "r") as f:
    code = f.read()

sell_logic_old = """
                if profit_pct <= -HARD_STOP_PCT:
                    reason = f"HARD STOP ({profit_pct*100:.2f}%)"
                    should_sell = True
                elif profit_pct >= HARD_TP_PCT:
                    reason = f"TAKE PROFIT ({profit_pct*100:.2f}%)"
                    should_sell = True
"""

sell_logic_new = """
                # Fallbacks to base config if not set
                tp_pct = pos.get('tp_pct', HARD_TP_PCT)
                sl_pct = pos.get('sl_pct', HARD_STOP_PCT)
                trail = pos.get('trail', False)
                trail_act = pos.get('trail_act', 0)
                trail_dist = pos.get('trail_dist', 0)
                
                if profit_pct <= -sl_pct:
                    reason = f"DYNAMIC SL ({profit_pct*100:.2f}%)"
                    should_sell = True
                elif profit_pct >= tp_pct and not trail:
                    reason = f"DYNAMIC TP ({profit_pct*100:.2f}%)"
                    should_sell = True
                elif trail and pos['peak'] > pos['entry'] * (1 + trail_act):
                    # Trailing logic: if price drops trail_dist from the peak
                    if current_price <= pos['peak'] * (1 - trail_dist):
                        reason = f"TRAILING STOP ({profit_pct*100:.2f}%)"
                        should_sell = True
"""

if "elif profit_pct >= HARD_TP_PCT:" in code:
    code = code.replace(sell_logic_old.strip(), sell_logic_new.strip())
    print("Sell logic updated.")
else:
    print("Could not find sell logic.")

with open("trade_daemon_v2.py", "w") as f:
    f.write(code)
