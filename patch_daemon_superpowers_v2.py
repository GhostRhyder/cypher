import re

with open("trade_daemon_v2.py", "r") as f:
    code = f.read()

# Make sure superpowers is imported
if "from superpowers import get_trade_params" not in code:
    code = "from superpowers import get_trade_params\n" + code

# Now we need to modify the PnL evaluation block in run_v2_daemon to use the custom params if they exist, else fallback.
# Wait, it's easier to store the params inside the active_positions dictionary when buying!

buy_logic = """
                    target = scan_market(exclude_symbols=list(active_positions.keys()))
                    if target:
                        params = get_trade_params(target)
                        if not params.trade:
                            log(f"[SUPERPOWERS] Blocked {target}: {params.reason}")
                            continue

                        trade_size_adjusted = trade_size * params.size_mult
                        
                        if execute_buy(target, trade_size_adjusted):
                            time.sleep(3)
                            price = get_ticker(target)
                            qty = get_coin_balance(target)
                            
                            if price and qty > 0:
                                active_positions[target] = {
                                    'entry': price,
                                    'peak': price,
                                    'quantity': qty,
                                    'start_time': int(time.time()),
                                    'cost_basis': trade_size_adjusted,
                                    'tp_pct': params.tp_pct,
                                    'sl_pct': params.sl_pct,
                                    'trail': params.trail,
                                    'trail_act': params.trail_act,
                                    'trail_dist': params.trail_dist,
                                    'regime': params.regime
                                }
                                log(f"[DEPLOYED] Added {target} at {price} (Regime: {params.regime}, Size: {trade_size_adjusted:.2f})")
"""

pattern_buy = re.compile(r"                    target = scan_market\(exclude_symbols=list\(active_positions\.keys\(\)\)\).*?log\(f\"\[DEPLOYED\] Added \{target\} at \{price\} \(Qty: \{qty\}\)\"\)", re.DOTALL)
if pattern_buy.search(code):
    code = pattern_buy.sub(buy_logic.strip(), code)
    print("Buy logic patched.")
else:
    print("Buy logic NOT found.")

# Now we must update the sell logic to use the custom params instead of hardcoded HARD_TP_PCT / HARD_SL_PCT
# The sell logic looks something like:
# for sym, pos in list(active_positions.items()):
#   price = get_ticker(sym)
#   if profit_pct <= -HARD_SL_PCT or profit_pct >= HARD_TP_PCT...

sell_logic_pattern = re.compile(r"for sym, pos in list\(active_positions\.items\(\)\):.*?(elif profit_pct >= HARD_TP_PCT:)", re.DOTALL)
# Actually, I should just grep the exact block to see what it is.

with open("trade_daemon_v2.py", "w") as f:
    f.write(code)

