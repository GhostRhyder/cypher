import re

with open('new_dashboard_patched.py', 'r') as f:
    code = f.read()

# Insert Spotter HTML
spotter_html = """
        <!-- TRADE SPOTTER -->
        <div class="card" id="spotter-card" style="margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #30363d; margin-bottom: 10px; padding-bottom: 5px;">
                <h3 style="margin: 0; border: none; padding: 0; color: #d2a8ff;">MARKET SPOTTER (4H/1D)</h3>
                <div id="spotter-time" style="font-size: 13px; color: #8b949e;">Last Scan: --:--</div>
            </div>
            <div id="spotter-data" style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                <p style="color: #8b949e;">Waiting for scanner data...</p>
            </div>
        </div>
"""
code = code.replace('<div class="grid">', spotter_html + '\n        <div class="grid">')

# Add JS logic to parse spotter_data inside updateDashboard()
js_logic = """
                // Render Spotter
                if (data.spotter_data && data.spotter_data.trend_trades) {
                    const spotterContainer = document.getElementById('spotter-data');
                    document.getElementById('spotter-time').innerText = "Last Scan: " + (data.spotter_data.scan_time ? data.spotter_data.scan_time.split('T')[1].substring(0,5) : "--:--");
                    let spotterHtml = '';
                    
                    const allTrades = [...(data.spotter_data.trend_trades || []), ...(data.spotter_data.range_trades || [])];
                    if (allTrades.length > 0) {
                        allTrades.forEach(trade => {
                            const typeColor = trade.type === 'LONG' ? '#3fb950' : '#da3633';
                            const tags = trade.signals ? trade.signals.map(s => `<span style="background: #30363d; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-right: 4px;">${s}</span>`).join('') : '';
                            
                            spotterHtml += `
                                <div style="background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 12px;">
                                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                                        <div style="font-weight: bold; font-size: 16px; color: #c9d1d9;">${trade.coin} <span style="font-size: 12px; color: #8b949e;">${trade.timeframe}</span></div>
                                        <div style="color: ${typeColor}; font-weight: bold;">${trade.type}</div>
                                    </div>
                                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 5px; font-size: 13px; margin-bottom: 8px; border-bottom: 1px dashed #30363d; padding-bottom: 8px;">
                                        <div><span style="color: #8b949e;">Entry:</span> <br>${trade.entry}</div>
                                        <div><span style="color: #8b949e;">Target:</span> <br><span style="color: #3fb950">${trade.tp}</span></div>
                                        <div><span style="color: #8b949e;">Stop:</span> <br><span style="color: #da3633">${trade.sl}</span></div>
                                    </div>
                                    <div style="font-size: 12px; color: #8b949e; margin-bottom: 8px; line-height: 1.4;">
                                        ${trade.thesis}
                                    </div>
                                    <div style="display: flex; justify-content: space-between; align-items: center;">
                                        <div>${tags}</div>
                                        <div style="font-size: 12px; color: #d2a8ff; font-weight: bold;">R:R ${trade.rr}</div>
                                    </div>
                                </div>
                            `;
                        });
                        spotterContainer.innerHTML = spotterHtml;
                    } else {
                        spotterContainer.innerHTML = `<div style="color: #8b949e; font-style: italic;">No setups found in recent scan.</div>`;
                    }
                }

                // Render Trades
"""
code = code.replace("// Live Trades", js_logic)

with open('new_dashboard_patched.py', 'w') as f:
    f.write(code)
