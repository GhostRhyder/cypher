import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cypher | Multi-System Dashboard</title>
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-family: monospace; margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { border-bottom: 1px solid #30363d; padding-bottom: 10px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
        .title { font-size: 24px; font-weight: bold; color: #58a6ff; }
        .status { padding: 5px 10px; border-radius: 5px; font-weight: bold; font-size: 14px; }
        .status.hunting { background-color: #1f6feb; color: white; }
        .status.deployed { background-color: #238636; color: white; }
        .status.cooldown { background-color: #da3633; color: white; }
        
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
        .card { background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 15px; }
        .card h3 { margin-top: 0; color: #8b949e; border-bottom: 1px solid #30363d; padding-bottom: 5px; }
        
        .log-box { background-color: #000; padding: 10px; border-radius: 4px; border: 1px solid #30363d; height: 300px; overflow-y: auto; font-size: 13px; color: #3fb950; }
        .log-line { margin-bottom: 4px; }
        
        table { width: 100%; border-collapse: collapse; font-size: 14px; }
        th, td { text-align: left; padding: 8px; border-bottom: 1px solid #30363d; }
        th { color: #8b949e; font-weight: normal; }
        
        .tab-btn { background: #30363d; color: #c9d1d9; border: none; padding: 5px 10px; margin-right: 5px; cursor: pointer; border-radius: 4px; font-family: monospace; }
        .tab-btn.active { background: #238636; color: white; }
        .btn-page { background: #238636; color: white; border: none; padding: 3px 8px; border-radius: 4px; cursor: pointer; }
        .btn-page:disabled { background: #30363d; color: #8b949e; cursor: not-allowed; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="title">CYPHER // MULTI-SYSTEM DASHBOARD</div>
        </div>
        
        <div class="grid">
            <!-- LEFT COLUMN: BINANCE (SWING) -->
            <div class="card" id="binance-card">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #30363d; margin-bottom: 10px; padding-bottom: 5px;">
                    <h3 style="margin: 0; border: none; padding: 0; color: #f3ba2f;">BINANCE SWING (4H)</h3>
                    <div id="status-binance" class="status hunting">LOADING...</div>
                </div>
                <div id="trade-data-binance">
                    <p style="color: #8b949e;">Waiting for daemon...</p>
                </div>
            </div>

            <!-- RIGHT COLUMN: PIONEX (SCALPER) -->
            <div class="card" id="pionex-card">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #30363d; margin-bottom: 10px; padding-bottom: 5px;">
                    <h3 style="margin: 0; border: none; padding: 0; color: #58a6ff;">PIONEX SCALPER</h3>
                    <div id="status-pionex" class="status hunting">LOADING...</div>
                </div>
                <div id="trade-data-pionex">
                    <p style="color: #8b949e;">Waiting for daemon...</p>
                </div>
            </div>
        </div>
        
        <!-- HISTORY TABLE (FULL WIDTH) -->
        <div class="card" style="margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 1px solid #30363d; margin-bottom: 15px; padding-bottom: 10px;">
                <div style="display: flex; flex-direction: column; gap: 10px;">
                    <h3 style="margin: 0; border: none; padding: 0;">TRADE HISTORY</h3>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <select id="history-filter" style="background: #0d1117; color: #c9d1d9; border: 1px solid #30363d; padding: 5px; border-radius: 4px;" onchange="handleFilterChange()">
                            <option value="ALL">All Trades</option>
                            <option value="BINANCE">Binance Only</option>
                            <option value="PIONEX">Pionex Only</option>
                        </select>
                        <div id="pionex-tabs" style="display: none; margin-left: 10px;">
                            <button id="tab-v3" class="tab-btn active" onclick="setPionexTab('V3')">V3 Trades</button>
                            <button id="tab-v2" class="tab-btn" onclick="setPionexTab('V2')">V2 Trades</button>
                        </div>
                    </div>
                </div>
                
                <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 5px;">
                    <div id="total-pnl" style="font-weight: bold; font-size: 15px;">Total PnL: $0.00</div>
                    <div id="pagination-controls" style="display: flex; gap: 10px; align-items: center;">
                        <button onclick="changePage(-1)" id="btn-prev" class="btn-page">Prev</button>
                        <span id="page-info" style="font-size: 13px; color: #8b949e;">Page 1 of 1</span>
                        <button onclick="changePage(1)" id="btn-next" class="btn-page">Next</button>
                    </div>
                </div>
            </div>
            
            <table id="history-table">
                <tr><th>System</th><th>Time</th><th>Coin</th><th>Dir</th><th>Result</th><th>PnL %</th><th>PnL $</th></tr>
                <tr><td colspan="7" style="color: #8b949e; text-align: center;">Loading history...</td></tr>
            </table>
        </div>

        <!-- LOGS (FULL WIDTH) -->
        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 1px solid #30363d; margin-bottom: 15px; padding-bottom: 5px;">
                <h3 style="margin: 0; border: none; padding: 0;">SYSTEM LOGS</h3>
                <select id="log-filter" style="background: #0d1117; color: #c9d1d9; border: 1px solid #30363d; padding: 5px; border-radius: 4px;" onchange="updateDashboard()">
                    <option value="ALL">All Logs</option>
                    <option value="BINANCE">Binance Only</option>
                    <option value="PIONEX">Pionex Only</option>
                </select>
            </div>
            <div class="log-box" id="log-box">
                Loading logs...
            </div>
        </div>
    </div>

    <script>
        let currentPage = 1;
        const itemsPerPage = 15;
        let currentPionexTab = 'V3';
        
        function formatDuration(startTime) {
            if (!startTime) return 'N/A';
            const now = new Date();
            // start_time is in seconds, convert to ms for Date object
            const start = new Date(startTime * 1000);
            let totalSeconds = Math.floor((now - start) / 1000);
            
            let hours = Math.floor(totalSeconds / 3600);
            totalSeconds %= 3600;
            let minutes = Math.floor(totalSeconds / 60);
            let seconds = totalSeconds % 60;

            const pad = (num) => num.toString().padStart(2, '0');
            return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
        }

        function formatTradeTime(ts) {
            if (!ts) return '';
            try {
                // Handle both string and number timestamps
                const date = new Date(ts);
                const hours = date.getHours().toString().padStart(2, '0');
                const minutes = date.getMinutes().toString().padStart(2, '0');
                const seconds = date.getSeconds().toString().padStart(2, '0');
                return `${hours}:${minutes}:${seconds}`;
            } catch (e) {
                return ts; // fallback to raw
            }
        }

        
        function setPionexTab(tab) {
            currentPionexTab = tab;
            document.getElementById('tab-v3').classList.remove('active');
            document.getElementById('tab-v2').classList.remove('active');
            if (tab === 'V3') document.getElementById('tab-v3').classList.add('active');
            if (tab === 'V2') document.getElementById('tab-v2').classList.add('active');
            currentPage = 1;
            updateDashboard();
        }
        
        function handleFilterChange() {
            currentPage = 1;
            const filter = document.getElementById('history-filter').value;
            const tabs = document.getElementById('pionex-tabs');
            if (filter === 'PIONEX') {
                tabs.style.display = 'block';
            } else {
                tabs.style.display = 'none';
            }
            updateDashboard();
        }
        
        function changePage(delta) {
            currentPage += delta;
            updateDashboard();
        }

        function renderLiveTrades(containerId, stateData, systemName) {
            const container = document.getElementById(containerId);
            const positions = stateData.positions || (stateData.active_positions ? Object.values(stateData.active_positions) : []);
            const currentState = stateData.state || "HUNTING";
            
            const statusBadge = document.getElementById(systemName === 'BINANCE' ? 'status-binance' : 'status-pionex');
            statusBadge.textContent = currentState;
            statusBadge.className = 'status ' + currentState.toLowerCase();
            
            if (positions.length > 0) {
                let html = '';
                positions.forEach(pos => {
                    const coin = pos.coin || pos.symbol;
                    const pnlPct = pos.pnl_pct || 0;
                    const pnlColor = pnlPct >= 0 ? '#3fb950' : '#da3633';
                    const pnlSign = pnlPct >= 0 ? '+' : '';
                    
                    const entryPrice = pos.entry_price || 0;
                    const currPrice = pos.current_price || 0;
                    const costBasis = pos.cost_basis || pos.amount_usdt || pos.amount_usdc || 0;
                    const tradeValue = costBasis * (1 + (pnlPct/100));

                    html += `
                    <div style="border-bottom: 1px solid #30363d; padding-bottom: 10px; margin-bottom: 10px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                            <div style="font-size: 16px; font-weight: bold; color: ${systemName === 'BINANCE' ? '#f3ba2f' : '#58a6ff'};">${coin}</div>
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 5px; font-size: 13px;">
                            <div><span style="color: #8b949e;">Size:</span> $${costBasis.toFixed(2)}</div>
                            <div style="font-weight: bold; color: ${pnlColor};">PnL: ${pnlSign}${pnlPct.toFixed(2)}%</div>
                            <div><span style="color: #8b949e;">Entry:</span> ${entryPrice}</div>
                            <div><span style="color: #8b949e;">Duration:</span> ${formatDuration(pos.start_time)}</div>
                            <div><span style="color: #8b949e;">Current:</span> ${currPrice}</div>
                        </div>
                    </div>
                    `;
                });
                container.innerHTML = html;
            } else {
                container.innerHTML = `
                    <p style="color: #3fb950; font-weight: bold;">HUNTING FOR TARGETS...</p>
                    <p style="color: #8b949e; font-size: 13px;">System is monitoring the market.</p>
                `;
            }
        }

        async function updateDashboard() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();
                
                // Live Trades
                renderLiveTrades('trade-data-binance', data.state_swing, 'BINANCE');
                renderLiveTrades('trade-data-pionex', data.state_v3, 'PIONEX');
                
                // History
                const filterHist = document.getElementById('history-filter').value;
                let allHistory = [];
                
                if (filterHist === 'ALL' || filterHist === 'PIONEX') {
                    (data.history_v3 || []).forEach(t => {
                        const ver = t.version || 'V2';
                        // If ALL, show everything Pionex. If PIONEX, filter by selected tab.
                        if (filterHist === 'PIONEX') {
                            if (ver === currentPionexTab) allHistory.push({...t, sys: 'PIONEX'});
                        } else {
                            allHistory.push({...t, sys: `PIONEX (${ver})`});
                        }
                    });
                }
                if (filterHist === 'ALL' || filterHist === 'BINANCE') {
                    (data.history_swing || []).forEach(t => allHistory.push({...t, sys: 'BINANCE'}));
                }
                
                allHistory.sort((a,b) => (b.timestamp || b.exit_time || "").localeCompare(a.timestamp || a.exit_time || ""));
                
                // Compute running total for filtered data
                let runningTotal = 0.0;
                allHistory.forEach(trade => {
                    let pnlUsdt = trade.pnl_usdt !== undefined ? trade.pnl_usdt : (trade.pnl_usdc || 0);
                    if (pnlUsdt === 0 && trade.cost_basis) {
                        pnlUsdt = trade.cost_basis * ((trade.pnl_pct || 0) / 100);
                    }
                    runningTotal += pnlUsdt;
                });
                
                const totalColor = runningTotal >= 0 ? '#3fb950' : '#da3633';
                const totalSign = runningTotal >= 0 ? '+' : '';
                document.getElementById('total-pnl').innerHTML = `Total ${allHistory.length} PnL: <span style="color: ${totalColor};">${totalSign}$${runningTotal.toFixed(2)}</span>`;
                
                // Pagination
                const totalItems = allHistory.length;
                const totalPages = Math.ceil(totalItems / itemsPerPage) || 1;
                if (currentPage > totalPages) currentPage = totalPages;
                if (currentPage < 1) currentPage = 1;
                
                document.getElementById('page-info').innerText = `Page ${currentPage} of ${totalPages}`;
                document.getElementById('btn-prev').disabled = currentPage === 1;
                document.getElementById('btn-next').disabled = currentPage === totalPages;
                
                const startIndex = (currentPage - 1) * itemsPerPage;
                const pageItems = allHistory.slice(startIndex, startIndex + itemsPerPage);
                
                const histBody = document.getElementById('history-table');
                let histRows = "<tr><th>System</th><th>Time</th><th>Coin</th><th>Dir</th><th>Result</th><th>PnL %</th><th>PnL $</th></tr>";
                
                pageItems.forEach(trade => {
                    const pnlPct = trade.pnl_pct || 0;
                    const pnlColor = pnlPct >= 0 ? '#3fb950' : '#da3633';
                    const pnlSign = pnlPct >= 0 ? '+' : '';
                    
                    let pnlUsdt = trade.pnl_usdt !== undefined ? trade.pnl_usdt : (trade.pnl_usdc || 0);
                    if (pnlUsdt === 0 && trade.cost_basis) {
                        pnlUsdt = trade.cost_basis * ((pnlPct || 0) / 100);
                    }
                    const pnlUsdtStr = (pnlUsdt >= 0 ? '+' : '') + '$' + pnlUsdt.toFixed(2);
                    
                    const sysColor = trade.sys === 'BINANCE' ? '#f3ba2f' : '#58a6ff';
                    
                    histRows += `
                        <tr>
                            <td style="color: ${sysColor};">${trade.sys}</td>
                            <td>${formatTradeTime(trade.timestamp || trade.exit_time)}</td>
                            <td>${trade.coin || trade.symbol || ''}</td>
                            <td>${trade.direction || "LONG"}</td>
                            <td style="color: ${pnlColor}; font-weight: bold;">${trade.result || trade.exit_reason || ''}</td>
                            <td style="color: ${pnlColor};">${pnlSign}${pnlPct.toFixed(2)}%</td>
                            <td style="color: ${pnlColor}; font-weight: bold;">${pnlUsdtStr}</td>
                        </tr>
                    `;
                });
                
                if (allHistory.length === 0) {
                    histRows += `<tr><td colspan="7" style="color: #8b949e; text-align: center;">No trades recorded matching filter.</td></tr>`;
                }
                histBody.innerHTML = histRows;
                
                // Logs
                const logFilter = document.getElementById('log-filter').value;
                const logBox = document.getElementById('log-box');
                
                let combinedLogs = [];
                if (logFilter === 'ALL' || logFilter === 'PIONEX') {
                    data.logs_v3.forEach(l => combinedLogs.push({text: l, sys: 'PIONEX'}));
                }
                if (logFilter === 'ALL' || logFilter === 'BINANCE') {
                    data.logs_swing.forEach(l => combinedLogs.push({text: l, sys: 'BINANCE'}));
                }
                
                combinedLogs.sort((a, b) => {
                    const matchA = a.text.match(/\[(202\d-[^\]]+)\]/);
                    const matchB = b.text.match(/\[(202\d-[^\]]+)\]/);
                    if (matchA && matchB) return matchA[1].localeCompare(matchB[1]);
                    return 0;
                });
                
                let newLogHTML = '';
                combinedLogs.slice(-50).forEach(line => {
                    const color = line.sys === 'BINANCE' ? '#f3ba2f' : '#58a6ff';
                    // Escape basic HTML safely to avoid injection if there were any
                    const safeText = line.text.replace(/</g, "&lt;").replace(/>/g, "&gt;");
                    newLogHTML += `<div class="log-line"><span style="color: ${color};">[${line.sys}]</span> ${safeText}</div>`;
                });
                
                // Only auto-scroll if user is already at the bottom to avoid annoyance
                const isScrolledToBottom = logBox.scrollHeight - logBox.clientHeight <= logBox.scrollTop + 50;
                logBox.innerHTML = newLogHTML;
                if (isScrolledToBottom) {
                    logBox.scrollTop = logBox.scrollHeight;
                }
                
            } catch (err) {
                console.error("Failed to fetch data:", err);
            }
        }
        
        // Initial setup
        handleFilterChange();
        setInterval(updateDashboard, 3000);
    </script>
</body>
</html>
"""

def read_json_safe(path, default):
    if not os.path.exists(path): return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return default

def read_logs_safe(path, lines=50):
    if not os.path.exists(path): return []
    try:
        with open(path, "r") as f:
            return [line.strip() for line in f.readlines()[-lines:] if line.strip()]
    except:
        return []

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))
            
        elif self.path == '/api/data':
            state_v3 = read_json_safe("state.json", {"state": "OFFLINE"})
            state_swing = read_json_safe("swing_state.json", {"state": "OFFLINE"})
            
            history_v3 = read_json_safe("history.json", [])
            history_swing = read_json_safe("swing_history.json", [])
            
            logs_v3 = read_logs_safe("trade_daemon_v2.log")
            logs_swing = read_logs_safe("swing_daemon.log")

            data = {
                "state_v3": state_v3,
                "state_swing": state_swing,
                "history_v3": history_v3,
                "history_swing": history_swing,
                "logs_v3": logs_v3,
                "logs_swing": logs_swing
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
            
        else:
            self.send_error(404)
            
    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    port = 8080
    server = HTTPServer(('0.0.0.0', port), DashboardHandler)
    print(f"✅ Multi-System Dashboard running on port {port}")
    server.serve_forever()
