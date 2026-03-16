
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
    