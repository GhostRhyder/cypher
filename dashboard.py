import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pionex_api_template import send_pionex_request

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cypher | V2 Auto-Compounder</title>
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-family: monospace; margin: 0; padding: 20px; }
        .container { max-width: 900px; margin: 0 auto; }
        .header { border-bottom: 1px solid #30363d; padding-bottom: 10px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
        .title { font-size: 24px; font-weight: bold; color: #58a6ff; }
        .status { padding: 5px 10px; border-radius: 5px; font-weight: bold; }
        .status.hunting { background-color: #1f6feb; color: white; }
        .status.deployed { background-color: #238636; color: white; }
        .status.cooldown { background-color: #da3633; color: white; }
        
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
        .card { background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 15px; }
        .card h3 { margin-top: 0; color: #8b949e; border-bottom: 1px solid #30363d; padding-bottom: 5px; }
        
        .log-box { background-color: #000; padding: 10px; border-radius: 4px; border: 1px solid #30363d; height: 300px; overflow-y: auto; font-size: 13px; color: #3fb950; }
        .log-line { margin-bottom: 4px; }
        
        table { width: 100%; border-collapse: collapse; }
        th, td { text-align: left; padding: 8px; border-bottom: 1px solid #30363d; }
        th { color: #8b949e; font-weight: normal; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="title">CYPHER // DAEMON V2</div>
            <div style="display: flex; align-items: center; gap: 15px;">
                <div id="usdt-balance" style="font-size: 18px; color: #3fb950; font-weight: bold; font-family: monospace;">USDT: --</div>
                <div id="ui-status" class="status hunting">LOADING...</div>
            </div>
        </div>
        
        <div class="grid">
            <div class="card">
                <h3>DAEMON LOGS (Live)</h3>
                <div class="log-box" id="log-box">
                    Loading logs...
                </div>
            </div>
            <div class="card">
                <h3>LIVE TRADE</h3>
                <div id="live-trade-data">
                    <p style="color: #8b949e;">Waiting for daemon...</p>
                </div>
            </div>
        </div>
        
        <div class="card" style="margin-bottom: 20px;">
            <h3>TRADE HISTORY (Last 50)</h3>
            <table id="history-table">
                <tr><th>Time</th><th>Coin</th><th>Result</th><th>PnL</th></tr>
                <tr><td colspan="4" style="color: #8b949e; text-align: center;">No trades recorded yet.</td></tr>
            </table>
        </div>
        
        <div class="card">
            <h3>PORTFOLIO BALANCES</h3>
            <table id="balances-table">
                <tr><th>Asset</th><th>Free Balance</th></tr>
                <tr><td colspan="2">Fetching...</td></tr>
            </table>
        </div>
    </div>

    <script>
        async function updateDashboard() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();
                
                // Update Logs
                const logBox = document.getElementById('log-box');
                logBox.innerHTML = '';
                
                data.logs.forEach(line => {
                    const div = document.createElement('div');
                    div.className = 'log-line';
                    div.textContent = line;
                    logBox.appendChild(div);
                });
                logBox.scrollTop = logBox.scrollHeight;
                
                // Update USDT Balance
                const usdtBal = data.balances['USDT'] || 0.0;
                document.getElementById('usdt-balance').textContent = `USDT: $${usdtBal.toFixed(2)}`;
                
                // Update Status Badge (Use state file for truth, fallback to logs)
                const stateData = data.state || {};
                const currentState = stateData.state || "HUNTING";
                
                const statusBadge = document.getElementById('ui-status');
                statusBadge.textContent = currentState;
                statusBadge.className = 'status ' + currentState.toLowerCase();
                
                // Update Live Trade Card
                const tradeBox = document.getElementById('live-trade-data');
                const positions = stateData.positions || [];
                
                if (positions.length > 0) {
                    let html = '';
                    positions.forEach(pos => {
                        const pnlColor = pos.pnl_pct >= 0 ? '#3fb950' : '#da3633';
                        const pnlSign = pos.pnl_pct >= 0 ? '+' : '';
                        
                        // Logic for Trailing Stop Status
                        const activationPct = 1.0; 
                        const trailDist = 1.0;     
                        
                        let tslStatus = '<span style="color: #8b949e;">INACTIVE (Needs +1%)</span>';
                        let tslPrice = "N/A";
                        
                        // Calculate Peak PnL
                        const peakPnl = ((pos.highest_price - pos.entry_price) / pos.entry_price) * 100;
                        
                        if (peakPnl >= activationPct) {
                            tslStatus = '<span style="color: #3fb950; font-weight: bold;">ACTIVE</span>';
                            const triggerPrice = pos.highest_price * (1 - (trailDist / 100));
                            tslPrice = triggerPrice.toPrecision(6);
                        } else {
                             const hardStop = pos.entry_price * (1 - 0.015);
                             tslStatus = `<span style="color: #8b949e;">INACTIVE</span>`;
                             tslPrice = `Hard Stop @ ${hardStop.toPrecision(6)}`;
                        }
                        
                        // Calculate Duration
                        let durationStr = "Just now";
                        if (pos.start_time) {
                            const now = Math.floor(Date.now() / 1000);
                            const diff = now - pos.start_time;
                            const hrs = Math.floor(diff / 3600);
                            const mins = Math.floor((diff % 3600) / 60);
                            durationStr = `${hrs}h ${mins}m`;
                        }

                        // Get Value
                        const tradeValue = pos.amount_usdt ? `$${pos.amount_usdt.toFixed(2)}` : "N/A";
                        const costBasis = pos.cost_basis ? `$${pos.cost_basis.toFixed(2)}` : "N/A";

                        html += `
                        <div style="border-bottom: 1px solid #30363d; padding-bottom: 10px; margin-bottom: 10px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                                <div style="font-size: 18px; font-weight: bold; color: #58a6ff;">${pos.coin}</div>
                                <div style="font-size: 12px; color: #8b949e;">${durationStr}</div>
                            </div>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 14px;">
                                <div><span style="color: #8b949e;">Size:</span> ${costBasis} -> <span style="color: ${pnlColor}; font-weight: bold;">${tradeValue}</span></div>
                                <div><span style="color: #8b949e;">Entry:</span> ${pos.entry_price}</div>
                                <div><span style="color: #8b949e;">Current:</span> ${pos.current_price}</div>
                                <div style="font-weight: bold; color: ${pnlColor};">PnL: ${pnlSign}${pos.pnl_pct.toFixed(2)}%</div>
                                
                                <div style="grid-column: span 2; border-top: 1px solid #30363d; margin-top: 5px; padding-top: 5px;">
                                    <div><span style="color: #8b949e;">Safety:</span> ${tslStatus} -> <span style="color: #da3633;">${tslPrice}</span></div>
                                </div>
                            </div>
                        </div>
                        `;
                    });
                    
                    // Add timestamp at bottom
                    html += `<div style="color: #8b949e; font-size: 12px; margin-top: 5px;">Last Update: ${stateData.timestamp}</div>`;
                    
                    tradeBox.innerHTML = html;
                
                } else if (currentState === "HUNTING") {
                    tradeBox.innerHTML = `
                        <p style="color: #3fb950; font-weight: bold;">HUNTING FOR TARGETS...</p>
                        <p style="color: #8b949e; font-size: 13px;">Scanning top 10 volume coins on 5M timeframe.</p>
                        <p style="color: #8b949e; font-size: 13px;">Waiting for S4/S5 signals.</p>
                        <div style="color: #8b949e; font-size: 12px; margin-top: 5px;">Last Update: ${stateData.timestamp || 'N/A'}</div>
                    `;
                } else {
                    tradeBox.innerHTML = `<p style="color: #da3633;">${currentState}</p>`;
                }
                
                // Update Balances
                const tbody = document.getElementById('balances-table');
                let rows = "<tr><th>Asset</th><th>Free Balance</th></tr>";
                for (const [coin, amount] of Object.entries(data.balances)) {
                    // Filter dust if needed, but showing all is fine for now
                    if (amount > 0.0) {
                        rows += `<tr><td>${coin}</td><td>${amount}</td></tr>`;
                    }
                }
                tbody.innerHTML = rows;
                
                // Update History Table
                const histBody = document.getElementById('history-table');
                if (data.history && data.history.length > 0) {
                    let histRows = "<tr><th>Time</th><th>Coin</th><th>Result</th><th>PnL</th></tr>";
                    data.history.forEach(trade => {
                        const pnlColor = trade.pnl_pct >= 0 ? '#3fb950' : '#da3633';
                        const pnlSign = trade.pnl_pct >= 0 ? '+' : '';
                        histRows += `
                            <tr>
                                <td>${trade.timestamp}</td>
                                <td>${trade.coin}</td>
                                <td style="color: ${pnlColor}; font-weight: bold;">${trade.result}</td>
                                <td style="color: ${pnlColor};">${pnlSign}${trade.pnl_pct.toFixed(2)}%</td>
                            </tr>
                        `;
                    });
                    histBody.innerHTML = histRows;
                }
                
            } catch (err) {
                console.error("Failed to fetch data:", err);
            }
        }
        
        // Poll every 3 seconds
        setInterval(updateDashboard, 3000);
        updateDashboard();
    </script>
</body>
</html>
"""

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))
            
        elif self.path == '/api/data':
            # Fetch Balances
            bals = {}
            try:
                res = send_pionex_request("GET", "/api/v1/account/balances")
                for item in res['data']['balances']:
                    free = float(item['free'])
                    if free > 0.0001:  # Simple dust filter for display
                        bals[item['coin']] = free
            except:
                bals = {"Error": 0.0}

            # Fetch Logs
            logs = []
            try:
                with open("trade_daemon_v2.log", "r") as f:
                    logs = [line.strip() for line in f.readlines()[-30:] if line.strip()]
            except:
                logs = ["Waiting for trade_daemon_v2.log..."]

            # Fetch State
            state = {}
            try:
                with open("state.json", "r") as f:
                    state = json.load(f)
            except:
                state = {"state": "OFFLINE", "coin": None, "pnl_pct": 0.0}

            # Fetch History
            history = []
            try:
                with open("history.json", "r") as f:
                    history = json.load(f)
                    # Reverse so newest is first
                    history.reverse()
            except:
                history = []

            data = {
                "balances": bals,
                "logs": logs,
                "state": state,
                "history": history
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
            
        else:
            self.send_error(404)

if __name__ == '__main__':
    port = 8080
    server = HTTPServer(('0.0.0.0', port), DashboardHandler)
    print(f"✅ Dashboard running on port {port}")
    server.serve_forever()
