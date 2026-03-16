import re

with open('new_dashboard_patched.py', 'r') as f:
    code = f.read()

# 1. New HTML for Sections 1, 2, 3
new_html = """
        <!-- SECTION 1: MARKET SPOTTER -->
        <div style="margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #30363d; margin-bottom: 10px; padding-bottom: 5px;">
                <h3 style="margin: 0; border: none; padding: 0; color: #00d4aa;">TREND TRADES</h3>
                <div class="section-count" id="trend-count" style="font-size: 13px; color: #8b949e; display: inline-block;">0/3</div>
                <button onclick="rescan()" style="background: #00d4aa; color: #080b0f; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-family: monospace; font-weight: bold; font-size: 11px;">↻ RESCAN</button>
            </div>
            <div id="trend-grid" class="card-grid" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;"></div>
        </div>

        <div style="margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #30363d; margin-bottom: 10px; padding-bottom: 5px;">
                <h3 style="margin: 0; border: none; padding: 0; color: #f0b429;">RANGE TRADES</h3>
                <div class="section-count" id="range-count" style="font-size: 13px; color: #8b949e;">0/3</div>
            </div>
            <div id="range-grid" class="card-grid" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;"></div>
        </div>

        <!-- SECTION 2: LIVE / IN ON IT -->
        <div class="card" style="margin-bottom: 20px; border-top: 3px solid #58a6ff;">
            <div style="display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 1px solid #30363d; margin-bottom: 15px; padding-bottom: 5px;">
                <h3 style="margin: 0; border: none; padding: 0; color: #58a6ff;">LIVE / IN ON IT</h3>
            </div>
            <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                <thead>
                    <tr><th>Coin</th><th>Type</th><th>Entry</th><th>Current</th><th>PnL %</th><th>PnL $</th><th>Duration</th><th>Status</th><th>Actions</th></tr>
                </thead>
                <tbody id="in-on-it-table">
                    <tr><td colspan="9" style="color: #8b949e; text-align: center;">No active manual trades.</td></tr>
                </tbody>
            </table>
        </div>

        <!-- SECTION 3: SPOTTER HISTORY -->
        <div class="card" style="margin-bottom: 20px; border-top: 3px solid #8b949e;">
            <div style="display: flex; flex-direction: column; gap: 10px; border-bottom: 1px solid #30363d; margin-bottom: 15px; padding-bottom: 10px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin: 0; border: none; padding: 0; color: #c9d1d9;">SPOTTER HISTORY</h3>
                </div>
                <div id="spotter-stats" style="display: flex; gap: 15px; font-size: 13px; color: #8b949e; background: #0d1117; padding: 10px; border-radius: 4px; border: 1px solid #30363d;">
                    <div>Total: <span id="sh-total" style="color:#c9d1d9">0</span></div>
                    <div>Win Rate: <span id="sh-winrate" style="color:#c9d1d9">0%</span></div>
                    <div>Total PnL: <span id="sh-pnl" style="color:#c9d1d9">$0.00</span></div>
                    <div>Avg Win: <span id="sh-avgwin" style="color:#3fb950">0%</span></div>
                    <div>Avg Loss: <span id="sh-avgloss" style="color:#da3633">0%</span></div>
                    <div>Best: <span id="sh-best" style="color:#3fb950">0%</span></div>
                    <div>Worst: <span id="sh-worst" style="color:#da3633">0%</span></div>
                </div>
            </div>
            <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                <thead>
                    <tr><th>Date/Time</th><th>Coin</th><th>Type</th><th>Entry</th><th>Exit</th><th>PnL %</th><th>PnL $</th><th>Duration</th><th>Result</th></tr>
                </thead>
                <tbody id="spotter-history-table">
                    <tr><td colspan="9" style="color: #8b949e; text-align: center;">No spotter history.</td></tr>
                </tbody>
            </table>
        </div>
"""

# Replace existing spotter section
code = re.sub(r'<!-- TRADE SPOTTER -->.*?(?=<div class="grid">)', new_html, code, flags=re.DOTALL)

# 2. Inject new JS State Management and logic inside <script>
js_state = """
        // --- SPOTTER STATE MANAGEMENT ---
        let inOnItTrades = JSON.parse(localStorage.getItem('cypher_in_on_it') || '[]');
        let spotterHistory = JSON.parse(localStorage.getItem('cypher_spotter_history') || '[]');
        let pulledIds = JSON.parse(localStorage.getItem('cypher_pulled_ids') || '[]');
        
        function saveSpotterState() {
            localStorage.setItem('cypher_in_on_it', JSON.stringify(inOnItTrades));
            localStorage.setItem('cypher_spotter_history', JSON.stringify(spotterHistory));
            localStorage.setItem('cypher_pulled_ids', JSON.stringify(pulledIds));
            renderSpotterDashboard();
        }

        // Expose latest spotter data globally for buttons
        let latestSpotterData = { trends: [], ranges: [] };

        function actionInOnIt(coin, type) {
            const trade = latestSpotterData.trends.find(t => t.coin === coin) || latestSpotterData.ranges.find(t => t.coin === coin);
            if (!trade) return;
            
            pulledIds.push(coin + type);
            inOnItTrades.push({
                id: Date.now().toString(),
                coin: trade.coin,
                type: trade.type || (type==='RANGE'?'GRID':'LONG'),
                entry: parseFloat(trade.entry || trade.range_low || 0),
                tp: parseFloat(trade.tp || trade.range_high || 0),
                sl: parseFloat(trade.sl || trade.range_low || 0),
                cost_basis: 100, // mock $100 size for tracking PnL $
                start_time: Date.now(),
                status_icon: type === 'RANGE' ? '⚡' : '↑'
            });
            saveSpotterState();
        }

        function actionPull(coin, type) {
            const trade = latestSpotterData.trends.find(t => t.coin === coin) || latestSpotterData.ranges.find(t => t.coin === coin);
            if (!trade) return;
            
            pulledIds.push(coin + type);
            spotterHistory.push({
                date: new Date().toLocaleString(),
                coin: trade.coin,
                type: trade.type || (type==='RANGE'?'GRID':'LONG'),
                entry: trade.entry || trade.range_low,
                exit: trade.tp || trade.range_high, // "Suggested" levels
                pnl_pct: 0,
                pnl_usd: 0,
                duration: '0m',
                result: 'PULLED'
            });
            saveSpotterState();
        }

        function closeTrade(id, result) {
            const idx = inOnItTrades.findIndex(t => t.id === id);
            if (idx === -1) return;
            const t = inOnItTrades[idx];
            
            const durationMs = Date.now() - t.start_time;
            const durationMins = Math.floor(durationMs / 60000);
            const durStr = durationMins > 60 ? `${(durationMins/60).toFixed(1)}h` : `${durationMins}m`;
            
            // Mock final PnL based on TP/SL
            let finalPct = 0;
            if (result === 'WIN') {
                finalPct = t.type === 'LONG' ? ((t.tp - t.entry)/t.entry)*100 : 5.0; // mock 5% win
            } else {
                finalPct = t.type === 'LONG' ? ((t.sl - t.entry)/t.entry)*100 : -5.0; // mock -5% loss
            }
            const finalUsd = (t.cost_basis * (finalPct/100)).toFixed(2);

            spotterHistory.push({
                date: new Date().toLocaleString(),
                coin: t.coin,
                type: t.type,
                entry: t.entry,
                exit: result === 'WIN' ? t.tp : t.sl,
                pnl_pct: finalPct,
                pnl_usd: parseFloat(finalUsd),
                duration: durStr,
                result: result
            });
            
            inOnItTrades.splice(idx, 1);
            saveSpotterState();
        }

        function renderSpotterDashboard() {
            // Render Live IN ON IT
            const tbody = document.getElementById('in-on-it-table');
            if (inOnItTrades.length === 0) {
                tbody.innerHTML = '<tr><td colspan="9" style="color: #8b949e; text-align: center;">No active manual trades.</td></tr>';
            } else {
                let html = '';
                inOnItTrades.forEach(t => {
                    // Mock current price fluctuation
                    const mockCurrent = t.entry * (1 + (Math.random() * 0.02 - 0.01));
                    const currentPct = ((mockCurrent - t.entry) / t.entry) * 100;
                    const currentUsd = t.cost_basis * (currentPct / 100);
                    
                    const pColor = currentPct >= 0 ? '#3fb950' : '#da3633';
                    const pSign = currentPct >= 0 ? '+' : '';
                    
                    const durationMins = Math.floor((Date.now() - t.start_time) / 60000);
                    const durStr = durationMins > 60 ? `${(durationMins/60).toFixed(1)}h` : `${durationMins}m`;

                    html += `
                    <tr>
                        <td style="font-weight:bold; color:#c9d1d9">${t.coin}</td>
                        <td>${t.type}</td>
                        <td>${t.entry.toFixed(4)}</td>
                        <td>${mockCurrent.toFixed(4)}</td>
                        <td style="color:${pColor}">${pSign}${currentPct.toFixed(2)}%</td>
                        <td style="color:${pColor}">${pSign}$${currentUsd.toFixed(2)}</td>
                        <td>${durStr}</td>
                        <td>${t.status_icon}</td>
                        <td>
                            <button onclick="closeTrade('${t.id}', 'WIN')" style="background:#238636; color:white; border:none; padding:2px 6px; border-radius:4px; cursor:pointer; font-size:11px;">CLOSE WIN</button>
                            <button onclick="closeTrade('${t.id}', 'LOSS')" style="background:#da3633; color:white; border:none; padding:2px 6px; border-radius:4px; cursor:pointer; font-size:11px;">CLOSE LOSS</button>
                        </td>
                    </tr>`;
                });
                tbody.innerHTML = html;
            }

            // Render History
            const hbody = document.getElementById('spotter-history-table');
            if (spotterHistory.length === 0) {
                hbody.innerHTML = '<tr><td colspan="9" style="color: #8b949e; text-align: center;">No spotter history.</td></tr>';
            } else {
                let html = '';
                // Reverse to show newest first
                const revHist = [...spotterHistory].reverse();
                
                let wins = 0, losses = 0;
                let totPnl = 0.0;
                let sumWin = 0.0, sumLoss = 0.0;
                let best = 0.0, worst = 0.0;

                revHist.forEach(t => {
                    const rColor = t.result === 'WIN' ? '#3fb950' : (t.result === 'LOSS' ? '#da3633' : '#8b949e');
                    const pColor = t.pnl_pct >= 0 && t.result !== 'PULLED' ? '#3fb950' : (t.pnl_pct < 0 ? '#da3633' : '#8b949e');
                    const pSign = t.pnl_pct > 0 ? '+' : '';
                    
                    if (t.result === 'WIN') { wins++; totPnl += t.pnl_usd; sumWin += t.pnl_pct; best = Math.max(best, t.pnl_pct); }
                    if (t.result === 'LOSS') { losses++; totPnl += t.pnl_usd; sumLoss += t.pnl_pct; worst = Math.min(worst, t.pnl_pct); }

                    html += `
                    <tr>
                        <td style="font-size:12px">${t.date}</td>
                        <td style="font-weight:bold; color:#c9d1d9">${t.coin}</td>
                        <td>${t.type}</td>
                        <td>${typeof t.entry === 'number' ? t.entry.toFixed(4) : t.entry}</td>
                        <td>${typeof t.exit === 'number' ? t.exit.toFixed(4) : t.exit}</td>
                        <td style="color:${pColor}">${t.result==='PULLED'?'-':(pSign+t.pnl_pct.toFixed(2)+'%')}</td>
                        <td style="color:${pColor}">${t.result==='PULLED'?'-':(pSign+'$'+t.pnl_usd.toFixed(2))}</td>
                        <td>${t.duration}</td>
                        <td style="color:${rColor}; font-weight:bold">${t.result}</td>
                    </tr>`;
                });
                hbody.innerHTML = html;

                // Update Stats
                const completed = wins + losses;
                document.getElementById('sh-total').innerText = spotterHistory.length;
                document.getElementById('sh-winrate').innerText = completed > 0 ? ((wins/completed)*100).toFixed(1) + '%' : '0%';
                
                const tSign = totPnl >= 0 ? '+' : '';
                const tColor = totPnl >= 0 ? '#3fb950' : '#da3633';
                const elPnl = document.getElementById('sh-pnl');
                elPnl.innerText = `${tSign}$${totPnl.toFixed(2)}`;
                elPnl.style.color = tColor;
                
                document.getElementById('sh-avgwin').innerText = wins > 0 ? '+' + (sumWin/wins).toFixed(2) + '%' : '0%';
                document.getElementById('sh-avgloss').innerText = losses > 0 ? (sumLoss/losses).toFixed(2) + '%' : '0%';
                document.getElementById('sh-best').innerText = best > 0 ? '+' + best.toFixed(2) + '%' : '0%';
                document.getElementById('sh-worst').innerText = worst < 0 ? worst.toFixed(2) + '%' : '0%';
            }
        }
        
        // Initial call
        window.addEventListener('load', () => {
            renderSpotterDashboard();
        });
        
        // --- END SPOTTER STATE MANAGEMENT ---
"""

code = code.replace("function createSparkline(data) {", js_state + "\n        function createSparkline(data) {")

# 3. Rewrite the spotter rendering inside updateDashboard
new_js_logic = """
                // Render Spotter Grid
                if (data.spotter_data) {
                    // Filter out pulled/accepted trades
                    const availTrends = (data.spotter_data.trend_trades || []).filter(t => !pulledIds.includes(t.coin + (t.type || 'LONG'))).slice(0, 3);
                    const availRanges = (data.spotter_data.range_trades || []).filter(t => !pulledIds.includes(t.coin + 'RANGE')).slice(0, 3);
                    
                    latestSpotterData.trends = availTrends;
                    latestSpotterData.ranges = availRanges;

                    document.getElementById('trend-count').innerText = `${availTrends.length}/3`;
                    let trendHtml = '';
                    availTrends.forEach(trade => {
                        trendHtml += `
                        <div style="background: #111820; border: 1px solid #1e2d3d; border-top: 3px solid #00d4aa; border-radius: 6px; padding: 12px; position: relative; display: flex; flex-direction: column;">
                            <div style="position: absolute; top: 10px; right: 10px; background: #00d4aa22; color: #00d4aa; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight:bold;">${trade.confidence}</div>
                            <div style="font-weight: bold; font-size: 16px; color: #ccd9e8; margin-bottom: 5px;">${trade.coin} <span style="font-size: 12px; color: #8899aa;">${trade.timeframe}</span></div>
                            <div style="color: #26de81; font-weight: bold; margin-bottom: 10px;">${trade.type}</div>
                            
                            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 5px; font-size: 13px; margin-bottom: 10px;">
                                <div><span style="color: #8899aa;">Entry:</span><br>${trade.entry}</div>
                                <div><span style="color: #8899aa;">TP:</span><br><span style="color: #26de81">${trade.tp}</span> <span style="font-size:11px;color:#8b949e">(${trade.tp_pct})</span></div>
                                <div><span style="color: #8899aa;">SL:</span><br><span style="color: #fc5c65">${trade.sl}</span> <span style="font-size:11px;color:#8b949e">(${trade.sl_pct})</span></div>
                            </div>
                            
                            <div style="font-size: 12px; color: #8899aa; line-height: 1.4; margin-bottom: 10px; flex-grow: 1; overflow: hidden; min-height: 40px;">
                                ${trade.thesis}
                            </div>
                            
                            <div style="display: flex; gap: 5px; margin-bottom: 10px; flex-wrap: wrap;">
                                ${(trade.signals || []).map(s => `<span style="background: ${(trade.active || []).includes(s) ? '#00d4aa' : '#1e2d3d'}; color: ${(trade.active || []).includes(s) ? '#080b0f' : '#8899aa'}; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight:bold;">${s}</span>`).join('')}
                                <span style="margin-left:auto; font-size: 11px; color: #d2a8ff; font-weight: bold;">R:R ${trade.rr}</span>
                            </div>
                            
                            <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 12px;">
                                <div>${createSparkline(trade.spark || [])}</div>
                                <div style="text-align: right;">
                                    <div style="font-size: 11px; color: #8899aa;">Expires in</div>
                                    <div style="font-size: 13px; color: #ccd9e8; font-family: monospace;">${trade.expires}</div>
                                </div>
                            </div>

                            <div style="display: flex; gap: 10px; border-top: 1px dashed #30363d; padding-top: 10px;">
                                <button onclick="actionInOnIt('${trade.coin}', 'TREND')" style="flex:1; background:#00d4aa; color:#080b0f; border:none; padding:6px; border-radius:4px; font-weight:bold; cursor:pointer;">IN ON IT</button>
                                <button onclick="actionPull('${trade.coin}', 'TREND')" style="flex:1; background:#1e2d3d; color:#8899aa; border:none; padding:6px; border-radius:4px; font-weight:bold; cursor:pointer;">PULL</button>
                            </div>
                        </div>`;
                    });
                    document.getElementById('trend-grid').innerHTML = trendHtml || '<div style="color:#8899aa; font-style:italic; padding: 10px; grid-column: 1 / -1; text-align:center;">No trend setups available.</div>';

                    document.getElementById('range-count').innerText = `${availRanges.length}/3`;
                    let rangeHtml = '';
                    availRanges.forEach(trade => {
                        rangeHtml += `
                        <div style="background: #111820; border: 1px solid #1e2d3d; border-top: 3px solid #f0b429; border-radius: 6px; padding: 12px; position: relative; display: flex; flex-direction: column;">
                            <div style="position: absolute; top: 10px; right: 10px; background: #f0b42922; color: #f0b429; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight:bold;">${trade.confidence}</div>
                            <div style="font-weight: bold; font-size: 16px; color: #ccd9e8; margin-bottom: 5px;">${trade.coin} <span style="font-size: 12px; color: #8899aa;">${trade.timeframe}</span></div>
                            <div style="color: #f0b429; font-weight: bold; margin-bottom: 10px;">GRID RANGE</div>
                            
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 5px; font-size: 13px; margin-bottom: 10px;">
                                <div><span style="color: #8899aa;">Range High:</span> ${trade.range_high}</div>
                                <div><span style="color: #8899aa;">Range Low:</span> ${trade.range_low}</div>
                                <div><span style="color: #8899aa;">Grid Levels:</span> ${trade.grid_levels}</div>
                                <div><span style="color: #8899aa;">Spacing:</span> ${trade.spacing}</div>
                            </div>
                            
                            <div style="font-size: 12px; color: #8899aa; line-height: 1.4; margin-bottom: 10px; flex-grow: 1; overflow: hidden; min-height: 40px;">
                                ${trade.thesis}
                            </div>
                            
                            <div style="display: flex; gap: 5px; margin-bottom: 10px; flex-wrap: wrap;">
                                ${(trade.signals || []).map(s => `<span style="background: ${(trade.active || []).includes(s) ? '#f0b429' : '#1e2d3d'}; color: ${(trade.active || []).includes(s) ? '#080b0f' : '#8899aa'}; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight:bold;">${s}</span>`).join('')}
                            </div>
                            
                            <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 12px;">
                                <div>${createSparkline(trade.spark || [])}</div>
                                <div style="text-align: right;">
                                    <div style="font-size: 11px; color: #8899aa;">Expires in</div>
                                    <div style="font-size: 13px; color: #ccd9e8; font-family: monospace;">${trade.expires}</div>
                                </div>
                            </div>

                            <div style="display: flex; gap: 10px; border-top: 1px dashed #30363d; padding-top: 10px;">
                                <button onclick="actionInOnIt('${trade.coin}', 'RANGE')" style="flex:1; background:#f0b429; color:#080b0f; border:none; padding:6px; border-radius:4px; font-weight:bold; cursor:pointer;">IN ON IT</button>
                                <button onclick="actionPull('${trade.coin}', 'RANGE')" style="flex:1; background:#1e2d3d; color:#8899aa; border:none; padding:6px; border-radius:4px; font-weight:bold; cursor:pointer;">PULL</button>
                            </div>
                        </div>`;
                    });
                    document.getElementById('range-grid').innerHTML = rangeHtml || '<div style="color:#8899aa; font-style:italic; padding: 10px; grid-column: 1 / -1; text-align:center;">No range setups available.</div>';

                    // Also refresh the LIVE / IN ON IT table to update dynamic prices
                    renderSpotterDashboard();
                }
"""

# Replace the inner block of spotter data render
code = re.sub(r'// Render Spotter\s*if \(data\.spotter_data.*?(?=(// Render Trades))', new_js_logic, code, flags=re.DOTALL)

with open('new_dashboard_patched.py', 'w') as f:
    f.write(code)

