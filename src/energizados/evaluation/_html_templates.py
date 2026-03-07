"""
CSS templates for evaluation HTML reports.

Extracted from report.py and index.py to improve maintainability (MEJORAS P3-11).
"""

REPORT_CSS = """\
* { box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    line-height: 1.6;
    color: #333;
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
    background-color: #f5f5f5;
}
.header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 30px;
    border-radius: 10px;
    margin-bottom: 30px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
.header h1 { margin: 0; font-size: 2.5em; }
.header p { margin: 10px 0 0 0; opacity: 0.9; }
.section {
    background: white;
    padding: 25px;
    margin-bottom: 20px;
    border-radius: 10px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.section h2 {
    color: #667eea;
    border-bottom: 2px solid #667eea;
    padding-bottom: 10px;
    margin-top: 0;
}
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin-top: 20px;
}
.metric-card {
    background: #f8f9fa;
    padding: 20px;
    border-radius: 8px;
    text-align: center;
    border-left: 4px solid #667eea;
}
.metric-card .value { font-size: 2.5em; font-weight: bold; color: #667eea; }
.metric-card .label { color: #666; font-size: 0.9em; text-transform: uppercase; letter-spacing: 1px; }
.plots-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
    gap: 20px;
    margin-top: 20px;
}
.plot-container { background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }
.plot-container img { max-width: 100%; height: auto; border-radius: 5px; }
.plot-container h3 { margin-top: 0; color: #667eea; }
.confusion-matrix {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    max-width: 300px;
    margin: 20px auto;
}
.cm-cell { background: #f8f9fa; padding: 20px; text-align: center; border-radius: 8px; }
.cm-cell.tp { border-left: 4px solid #28a745; }
.cm-cell.tn { border-left: 4px solid #6c757d; }
.cm-cell.fp { border-left: 4px solid #dc3545; }
.cm-cell.fn { border-left: 4px solid #ffc107; }
.cm-cell .value { font-size: 2em; font-weight: bold; }
.cm-cell .label { font-size: 0.8em; color: #666; }
.calibration-info {
    background: #e8f4f8;
    padding: 15px 20px;
    border-radius: 8px;
    border-left: 4px solid #17a2b8;
    margin-top: 10px;
}
.calibration-info p { margin: 4px 0; color: #333; font-size: 0.95em; }
.footer { text-align: center; padding: 20px; color: #666; font-size: 0.9em; }
"""

INDEX_CSS = """\
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    line-height: 1.6;
    color: #333;
    background-color: #f5f5f5;
    padding: 20px;
}
.header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 30px 35px;
    border-radius: 10px;
    margin-bottom: 30px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
.header h1 { font-size: 2em; margin-bottom: 5px; }
.header p { opacity: 0.85; font-size: 0.95em; }
.summary-bar { display: flex; gap: 15px; margin-bottom: 25px; flex-wrap: wrap; }
.summary-card {
    background: white;
    padding: 15px 20px;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.07);
    border-left: 4px solid #667eea;
    min-width: 140px;
}
.summary-card .value { font-size: 1.8em; font-weight: bold; color: #667eea; }
.summary-card .label { font-size: 0.8em; color: #888; text-transform: uppercase; letter-spacing: 0.5px; }
.section {
    background: white;
    border-radius: 10px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.08);
    overflow: hidden;
    margin-bottom: 20px;
}
.section-header { padding: 18px 25px; border-bottom: 2px solid #667eea; }
.section-header h2 { color: #667eea; font-size: 1.2em; }
table { width: 100%; border-collapse: collapse; font-size: 0.92em; }
thead th {
    background: #f8f9fa;
    padding: 12px 16px;
    text-align: left;
    font-weight: 600;
    color: #555;
    text-transform: uppercase;
    font-size: 0.78em;
    letter-spacing: 0.5px;
    border-bottom: 1px solid #e9ecef;
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
}
thead th.no-sort { cursor: default; }
thead th:not(.no-sort):hover { background: #e9ecef; color: #333; }
thead th.sorted-asc::after { content: " ▲"; color: #667eea; }
thead th.sorted-desc::after { content: " ▼"; color: #667eea; }
tbody tr { border-bottom: 1px solid #f0f0f0; transition: background 0.15s; }
tbody tr:hover { background: #f8f9ff; }
tbody tr.selected { background: #eef0ff !important; }
tbody tr:last-child { border-bottom: none; }
td { padding: 12px 16px; vertical-align: middle; }
td.run-name {
    font-family: 'SF Mono', 'Fira Code', 'Courier New', monospace;
    font-size: 0.88em;
    color: #444;
    font-weight: 500;
}
td.metric { text-align: right; font-variant-numeric: tabular-nums; font-weight: 500; }
td.metric.high { color: #28a745; }
td.metric.mid { color: #ffc107; }
td.metric.low { color: #dc3545; }
td.metric.na { color: #999; }
.report-link {
    display: inline-block;
    padding: 5px 12px;
    background: #667eea;
    color: white;
    text-decoration: none;
    border-radius: 5px;
    font-size: 0.82em;
    font-weight: 500;
    transition: background 0.15s;
}
.report-link:hover { background: #5a6fd6; }
.no-runs { padding: 50px; text-align: center; color: #aaa; font-size: 1.05em; }
.footer { text-align: center; padding: 20px; color: #aaa; font-size: 0.85em; }
.row-select { cursor: pointer; width: 15px; height: 15px; accent-color: #667eea; }
#comparison-panel {
    display: none;
    background: white;
    border-radius: 10px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    overflow: hidden;
    margin-bottom: 20px;
    border: 2px solid #667eea;
}
#comparison-panel .section-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    display: flex;
    align-items: center;
    justify-content: space-between;
}
#comparison-panel .section-header h2 { color: white; border-bottom: none; padding-bottom: 0; }
.btn-close-compare {
    background: rgba(255,255,255,0.2);
    border: none;
    color: white;
    padding: 5px 14px;
    border-radius: 5px;
    cursor: pointer;
    font-size: 0.85em;
}
.btn-close-compare:hover { background: rgba(255,255,255,0.35); }
#comparison-panel table td:first-child {
    background: #f8f9fa;
    font-weight: 600;
    color: #555;
    font-size: 0.82em;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.compare-bar {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%);
    background: #667eea;
    color: white;
    padding: 12px 20px;
    border-radius: 30px;
    box-shadow: 0 4px 16px rgba(102,126,234,0.5);
    display: none;
    align-items: center;
    gap: 12px;
    z-index: 100;
    font-size: 0.9em;
    white-space: nowrap;
}
.compare-bar.visible { display: flex; }
.btn-compare {
    background: white;
    color: #667eea;
    border: none;
    padding: 7px 16px;
    border-radius: 20px;
    cursor: pointer;
    font-weight: 600;
    font-size: 0.9em;
}
.btn-compare:hover { background: #f0f0f0; }
.btn-clear-compare {
    background: transparent;
    color: white;
    border: 1px solid rgba(255,255,255,0.5);
    padding: 7px 14px;
    border-radius: 20px;
    cursor: pointer;
    font-size: 0.9em;
}
.btn-clear-compare:hover { background: rgba(255,255,255,0.15); }
"""
