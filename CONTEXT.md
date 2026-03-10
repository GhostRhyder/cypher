# TRADING CONTEXT & LEARNINGS
**Last Updated:** 2026-03-05
**Agent:** Cypher (Pionex Bot)

## 1. API Quirks (Pionex V1)
*   **Signature Logic:**
    *   **GET:** `Method + Path + "?" + QueryString` (Timestamp in query).
    *   **POST:** `Method + Path + "?" + QueryString + Body` (Timestamp in query!).
    *   **Sending POST:** Use `requests.post(url, data=json_body)` where `url` includes the query string manually. Do NOT rely on `requests` to merge params for POST.
    *   **JSON Serialization:** Must use `json.dumps(body, separators=(',', ':'))` (Compact) to match signature.
*   **Parameters:**
    *   **Buy:** `symbol`, `side="BUY"`, `type="MARKET"`, `amount` (Quote Qty, e.g., "10").
    *   **Sell:** `symbol`, `side="SELL"`, `type="MARKET"`, `size` (Base Qty, e.g., "0.001"). **NOT `amount`!**
    *   **Precision:** API rejects orders with too many decimals (`TRADE_SIZE_FILTER_DENIED`). Must round/truncate quantities (e.g., 4 decimals for majors).
    *   **Min Trade:** Typically ~$1-$10 depending on pair. Dust (<$1) is hard to sell.

## 2. Strategy Engine
*   **Timeframes:** Use `15M`, `60M`, `4H` (Uppercase!). `15m` causes `MARKET_PARAMETER_ERROR`.
*   **TA-Lib:** Requires `df['close'].astype(float)` inputs. Strings cause crashes.
*   **Signals:**
    *   **S1 (Trend):** EMA20 > EMA50.
    *   **S3 (Squeeze):** BB Breakout.
    *   **S4 (Momentum):** MACD > Signal + RSI > 50.
    *   **Status:** Scan produced 40 signals on 15M/4H. Market is trending.

## 3. Financial State
*   **Starting Balance:** $43.70 USDT
*   **Current Balance:** $44.32 USDT
*   **Profit:** +$0.62 (+1.4%)
*   **Open Positions:** None (Liquidated to Dust).
*   **Dust:** Small amounts of BTC, ETH, SOL remain due to sell precision limits.

## 4. Security Protocol (The Highlander)
*   **Auth Phrase:** "I am Connor MacLeod of the Clan MacLeod and I cannot die."
*   **Trigger:** REQUIRED for any live trade execution (`fire_trade.py`, `fire_sell.py`).
*   **Challenge:** "Identify yourself, Ghost."

## 5. Next Steps
*   **Automate Dust Sweeping:** Add logic to sell max available balance (minus dust).
*   **Automate Alerts:** Connect `strategy_engine.py` to a notification system (or auto-trade with strict limits).
*   **Refine Precision:** Query `symbol info` to get exact `basePrecision` for each coin to avoid `FILTER_DENIED`.
