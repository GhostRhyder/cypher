import re

with open('new_dashboard_patched.py', 'r') as f:
    target = f.read()

with open('cypher_spotter_dashboard.html', 'r') as f:
    source = f.read()

# 1. Styles
styles_match = re.search(r'<style>(.*?)</style>', source, re.DOTALL)
source_styles = styles_match.group(1) if styles_match else ""
# Remove some body/generic resets from source_styles to avoid messing up main dash
source_styles = re.sub(r'body\s*{.*?}', '', source_styles, flags=re.DOTALL)
source_styles = re.sub(r'\*\s*{.*?}', '', source_styles, flags=re.DOTALL)

target = target.replace('</style>', source_styles + '\n    </style>')

# 2. Scanning overlay HTML
overlay_html = """
<!-- Scanning overlay -->
<div class="scanning-overlay" id="scanOverlay">
  <div class="scan-text">CYPHER // SCANNING</div>
  <div class="scan-progress"><div class="scan-progress-bar"></div></div>
  <div class="scan-log" id="scanLog">
    Initialising market scanner...<br>
    Loading Pionex futures universe...<br>
    <span id="scanStatus">Analysing 4H timeframes...</span>
  </div>
</div>
"""
target = target.replace('<body>', '<body>\n' + overlay_html)

# 3. Spotter HTML
spotter_html = """
        <!-- TRADE SPOTTER -->
        <div style="margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #30363d; margin-bottom: 10px; padding-bottom: 5px;">
                <h3 style="margin: 0; border: none; padding: 0; color: #00d4aa;">TREND TRADES</h3>
                <div class="section-count" id="trend-count" style="font-size: 13px; color: #8b949e; display: inline-block;">0/3</div>
                <button onclick="rescan()" style="background: #00d4aa; color: #080b0f; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-family: monospace; font-weight: bold; font-size: 11px;">↻ RESCAN</button>
            </div>
            <div id="trend-grid" class="card-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px;"></div>
        </div>

        <div style="margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #30363d; margin-bottom: 10px; padding-bottom: 5px;">
                <h3 style="margin: 0; border: none; padding: 0; color: #f0b429;">RANGE TRADES</h3>
                <div class="section-count" id="range-count" style="font-size: 13px; color: #8b949e;">0/3</div>
            </div>
            <div id="range-grid" class="card-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px;"></div>
        </div>
"""
target = re.sub(r'<!-- TRADE SPOTTER -->.*?(?=<div class="grid">)', spotter_html, target, flags=re.DOTALL)

# 4. Spotter JS Helper Functions
js_helpers = """
        function createSparkline(data) {
            if (!data || !data.length) return '';
            const max = Math.max(...data);
            const min = Math.min(...data);
            const range = max - min || 1;
            let html = '<div style="display: flex; align-items: flex-end; height: 20px; gap: 2px;">';
            data.slice(-10).forEach(val => {
                const height = Math.max(10, ((val - min) / range) * 100);
                html += `<div style="width: 4px; background: #3fb950; height: ${height}%;"></div>`;
            });
            html += '</div>';
            return html;
        }

        async function rescan() {
            const overlay = document.getElementById('scanOverlay');
            overlay.classList.add('active');
            
            // Just simulate the visual effect since we don't have a direct execute route yet
            setTimeout(() => {
                document.getElementById('scanStatus').innerText = "Scanning range setups...";
            }, 1000);
            
            setTimeout(() => {
                document.getElementById('scanStatus').innerText = "Finalising report...";
            }, 2000);

            setTimeout(() => {
                overlay.classList.remove('active');
                updateDashboard(); // fetch fresh data
            }, 3000);
        }
"""
target = target.replace('<script>', '<script>\n' + js_helpers)


# 5. JS Rendering inside updateDashboard
new_js_logic = """
                // Render Spotter
                if (data.spotter_data) {
                    const trends = data.spotter_data.trend_trades || [];
                    document.getElementById('trend-count').innerText = `${trends.length}/3`;
                    let trendHtml = '';
                    trends.forEach(trade => {
                        trendHtml += `
                        <div style="background: #111820; border: 1px solid #1e2d3d; border-top: 3px solid #00d4aa; border-radius: 6px; padding: 12px; position: relative;">
                            <div style="position: absolute; top: 10px; right: 10px; background: #00d4aa22; color: #00d4aa; padding: 2px 6px; border-radius: 4px; font-size: 11px;">${trade.confidence}</div>
                            <div style="font-weight: bold; font-size: 16px; color: #ccd9e8; margin-bottom: 5px;">${trade.coin} <span style="font-size: 12px; color: #8899aa;">${trade.timeframe}</span></div>
                            <div style="color: #26de81; font-weight: bold; margin-bottom: 10px;">${trade.type}</div>
                            
                            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 5px; font-size: 13px; margin-bottom: 10px;">
                                <div><span style="color: #8899aa;">Entry:</span><br>${trade.entry}</div>
                                <div><span style="color: #8899aa;">TP:</span><br><span style="color: #26de81">${trade.tp} (${trade.tp_pct})</span></div>
                                <div><span style="color: #8899aa;">SL:</span><br><span style="color: #fc5c65">${trade.sl} (${trade.sl_pct})</span></div>
                            </div>
                            
                            <div style="font-size: 12px; color: #8899aa; line-height: 1.4; margin-bottom: 10px; height: 50px; overflow: hidden;">
                                ${trade.thesis}
                            </div>
                            
                            <div style="display: flex; gap: 5px; margin-bottom: 10px; flex-wrap: wrap;">
                                ${(trade.signals || []).map(s => `<span style="background: ${(trade.active || []).includes(s) ? '#00d4aa' : '#1e2d3d'}; color: ${(trade.active || []).includes(s) ? '#080b0f' : '#8899aa'}; padding: 2px 6px; border-radius: 4px; font-size: 10px;">${s}</span>`).join('')}
                            </div>
                            
                            <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-top: auto;">
                                <div>${createSparkline(trade.spark || [])}</div>
                                <div style="text-align: right;">
                                    <div style="font-size: 11px; color: #8899aa;">Expires in</div>
                                    <div style="font-size: 13px; color: #ccd9e8;">${trade.expires}</div>
                                </div>
                            </div>
                        </div>`;
                    });
                    document.getElementById('trend-grid').innerHTML = trendHtml || '<div style="color:#8899aa; font-style:italic; padding: 10px;">No trend setups</div>';

                    const ranges = data.spotter_data.range_trades || [];
                    document.getElementById('range-count').innerText = `${ranges.length}/3`;
                    let rangeHtml = '';
                    ranges.forEach(trade => {
                        rangeHtml += `
                        <div style="background: #111820; border: 1px solid #1e2d3d; border-top: 3px solid #f0b429; border-radius: 6px; padding: 12px; position: relative;">
                            <div style="position: absolute; top: 10px; right: 10px; background: #f0b42922; color: #f0b429; padding: 2px 6px; border-radius: 4px; font-size: 11px;">${trade.confidence}</div>
                            <div style="font-weight: bold; font-size: 16px; color: #ccd9e8; margin-bottom: 5px;">${trade.coin} <span style="font-size: 12px; color: #8899aa;">${trade.timeframe}</span></div>
                            <div style="color: #f0b429; font-weight: bold; margin-bottom: 10px;">GRID</div>
                            
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 5px; font-size: 13px; margin-bottom: 10px;">
                                <div><span style="color: #8899aa;">Range High:</span> ${trade.range_high}</div>
                                <div><span style="color: #8899aa;">Range Low:</span> ${trade.range_low}</div>
                                <div><span style="color: #8899aa;">Grid Levels:</span> ${trade.grid_levels}</div>
                                <div><span style="color: #8899aa;">Spacing:</span> ${trade.spacing}</div>
                            </div>
                            
                            <div style="font-size: 12px; color: #8899aa; line-height: 1.4; margin-bottom: 10px; height: 50px; overflow: hidden;">
                                ${trade.thesis}
                            </div>
                            
                            <div style="display: flex; gap: 5px; margin-bottom: 10px; flex-wrap: wrap;">
                                ${(trade.signals || []).map(s => `<span style="background: ${(trade.active || []).includes(s) ? '#f0b429' : '#1e2d3d'}; color: ${(trade.active || []).includes(s) ? '#080b0f' : '#8899aa'}; padding: 2px 6px; border-radius: 4px; font-size: 10px;">${s}</span>`).join('')}
                            </div>
                            
                            <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-top: auto;">
                                <div>${createSparkline(trade.spark || [])}</div>
                                <div style="text-align: right;">
                                    <div style="font-size: 11px; color: #8899aa;">Expires in</div>
                                    <div style="font-size: 13px; color: #ccd9e8;">${trade.expires}</div>
                                </div>
                            </div>
                        </div>`;
                    });
                    document.getElementById('range-grid').innerHTML = rangeHtml || '<div style="color:#8899aa; font-style:italic; padding: 10px;">No range setups</div>';
                }
                // Render Trades
"""
target = re.sub(r'// Render Spotter.*?(?=(// Render Trades))', new_js_logic, target, flags=re.DOTALL)

with open('new_dashboard_patched.py', 'w') as f:
    f.write(target)

