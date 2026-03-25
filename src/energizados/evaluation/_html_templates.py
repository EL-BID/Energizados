"""
CSS templates for evaluation HTML reports.

Extracted from report.py and index.py to improve maintainability (MEJORAS P3-11).
Shared CSS with CSS custom properties and dark mode support (Phase 1).
"""

SHARED_CSS = """\
/* ── CSS Custom Properties ─────────────────────────────────────────────── */
:root {
    --primary: #667eea;
    --primary-dark: #5a6fd6;
    --secondary: #764ba2;
    --positive: #28a745;
    --negative: #dc3545;
    --warning: #ffc107;
    --neutral: #6c757d;
    --bg: #f5f5f5;
    --surface: #ffffff;
    --surface-alt: #f8f9fa;
    --text: #333333;
    --text-muted: #666666;
    --text-faint: #999999;
    --border: #e9ecef;
    --shadow: rgba(0,0,0,0.1);
    --shadow-sm: rgba(0,0,0,0.07);
    --header-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
/* Dark mode via .dark class on <html> */
html.dark {
    --primary: #818cf8;
    --primary-dark: #6366f1;
    --secondary: #a78bfa;
    --positive: #34d399;
    --negative: #f87171;
    --warning: #fbbf24;
    --neutral: #94a3b8;
    --bg: #0f172a;
    --surface: #1e293b;
    --surface-alt: #334155;
    --text: #e2e8f0;
    --text-muted: #94a3b8;
    --text-faint: #64748b;
    --border: #334155;
    --shadow: rgba(0,0,0,0.4);
    --shadow-sm: rgba(0,0,0,0.3);
    --header-gradient: linear-gradient(135deg, #3730a3 0%, #5b21b6 100%);
}
/* ── Dark mode toggle button ─────────────────────────────────────────── */
.dark-toggle {
    position: absolute;
    top: 16px;
    right: 20px;
    background: rgba(255,255,255,0.15);
    border: 1px solid rgba(255,255,255,0.3);
    color: white;
    padding: 6px 14px;
    border-radius: 20px;
    cursor: pointer;
    font-size: 0.82em;
    font-weight: 500;
    transition: background 0.2s;
}
.dark-toggle:hover { background: rgba(255,255,255,0.25); }
/* ── Print styles ─────────────────────────────────────────────────────── */
@media print {
    .sidebar, .dark-toggle, .compare-bar, #comparison-panel, .search-row,
    .plot-maximize-btn, .plot-modal { display: none !important; }
    .layout { display: block !important; }
    .main { margin: 0 !important; padding: 0 !important; }
    .header { background: none !important; color: #333 !important; border-bottom: 2px solid #667eea; }
    .section { box-shadow: none !important; border: 1px solid #ddd; }
    .plot-header { display: block !important; }
    .plot-header h3 { text-align: center; }
}
/* ── Dark mode toggle JS ──────────────────────────────────────────────── */
"""

_DARK_TOGGLE_JS = """\
<script>
(function(){
    var root = document.documentElement;
    var btn = document.getElementById('dark-toggle-btn');
    if (!btn) return;
    var saved = localStorage.getItem('energizados-dark');
    if (saved === '1') root.classList.add('dark');
    btn.textContent = root.classList.contains('dark') ? '☀ Light' : '☾ Dark';
    btn.addEventListener('click', function(){
        root.classList.toggle('dark');
        localStorage.setItem('energizados-dark', root.classList.contains('dark') ? '1' : '0');
        btn.textContent = root.classList.contains('dark') ? '☀ Light' : '☾ Dark';
    });
})();
</script>
"""

REPORT_CSS = SHARED_CSS + """\
/* ── Base ─────────────────────────────────────────────────────────────── */
* { box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    line-height: 1.6;
    color: var(--text);
    background-color: var(--bg);
    margin: 0;
    padding: 0;
}
/* ── Layout: sidebar + main ───────────────────────────────────────────── */
.layout {
    display: flex;
    min-height: 100vh;
}
.sidebar {
    width: 220px;
    min-width: 200px;
    background: var(--surface);
    border-right: 1px solid var(--border);
    padding: 20px 0;
    position: sticky;
    top: 0;
    height: 100vh;
    overflow-y: auto;
    flex-shrink: 0;
    box-shadow: 2px 0 4px var(--shadow-sm);
}
.sidebar-title {
    font-size: 0.7em;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text-faint);
    padding: 0 16px 8px 16px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 8px;
}
.sidebar a {
    display: block;
    padding: 8px 16px;
    color: var(--text-muted);
    text-decoration: none;
    font-size: 0.88em;
    border-left: 3px solid transparent;
    transition: all 0.15s;
}
.sidebar a:hover {
    color: var(--primary);
    background: var(--surface-alt);
    border-left-color: var(--primary);
}
.main {
    flex: 1;
    padding: 24px;
    min-width: 0;
}
@media (max-width: 900px) {
    .sidebar { display: none; }
    .main { padding: 16px; }
}
/* ── Header ───────────────────────────────────────────────────────────── */
.header {
    background: var(--header-gradient);
    color: white;
    padding: 30px;
    border-radius: 10px;
    margin-bottom: 30px;
    box-shadow: 0 4px 6px var(--shadow);
    position: relative;
}
.header h1 { margin: 0; font-size: 2.2em; }
.header p { margin: 10px 0 0 0; opacity: 0.9; }
.experiment-description {
    margin-top: 16px;
    padding: 10px 16px;
    background: rgba(255,255,255,0.15);
    border-left: 4px solid rgba(255,255,255,0.6);
    border-radius: 4px;
    font-size: 0.95em;
    white-space: pre-wrap;
    opacity: 1 !important;
}
/* ── Sections ─────────────────────────────────────────────────────────── */
.section {
    background: var(--surface);
    padding: 25px;
    margin-bottom: 20px;
    border-radius: 10px;
    box-shadow: 0 2px 4px var(--shadow);
}
.section h2 {
    color: var(--primary);
    border-bottom: 2px solid var(--primary);
    padding-bottom: 10px;
    margin-top: 0;
}
/* ── Metrics grid ─────────────────────────────────────────────────────── */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 16px;
    margin-top: 20px;
}
.metric-card {
    background: var(--surface-alt);
    padding: 20px;
    border-radius: 8px;
    text-align: center;
    border-left: 4px solid var(--primary);
}
.metric-card .value { font-size: 2.2em; font-weight: bold; color: var(--primary); }
.metric-card .label { color: var(--text-muted); font-size: 0.85em; text-transform: uppercase; letter-spacing: 1px; }
/* ── Plots grid ───────────────────────────────────────────────────────── */
.plots-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
    gap: 24px;
    margin-top: 20px;
}
.plot-container {
    background: var(--surface-alt);
    border-radius: 12px;
    padding: 16px;
    text-align: center;
    box-shadow: 0 2px 8px var(--shadow-sm);
    position: relative;
}
.plot-container:hover { box-shadow: 0 4px 12px var(--shadow); }
.plot-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}
.plot-header h3 {
    margin: 0;
    color: var(--primary);
    font-size: 1.1em;
}
.plot-maximize-btn {
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 4px 10px;
    cursor: pointer;
    font-size: 1.2em;
    line-height: 1;
    color: var(--text-muted);
    transition: all 0.2s;
}
.plot-maximize-btn:hover {
    background: var(--primary);
    color: white;
    border-color: var(--primary);
}
.plot-content { position: relative; }
.plot-container img { max-width: 100%; height: auto; border-radius: 6px; }
/* Plotly chart containers need explicit height */
.plot-content .js-plotly-plot { width: 100% !important; }

/* Fullscreen modal for maximized plots */
.plot-modal {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.85);
    z-index: 9999;
    padding: 20px;
    box-sizing: border-box;
}
.plot-modal.active { display: flex; flex-direction: column; align-items: center; justify-content: center; }
.plot-modal-content {
    background: var(--surface);
    border-radius: 12px;
    padding: 20px;
    width: min(92vw, 1200px);
    height: 88vh;
    overflow: hidden;
    position: relative;
    display: flex;
    flex-direction: column;
}
.plot-modal-close {
    position: absolute;
    top: 10px;
    right: 15px;
    background: transparent;
    border: none;
    font-size: 2em;
    color: var(--text-muted);
    cursor: pointer;
    line-height: 1;
    padding: 5px;
}
.plot-modal-close:hover { color: var(--negative); }
.plot-modal-title {
    margin: 0 0 12px 0;
    color: var(--primary);
    font-size: 1.3em;
    padding-right: 40px;
    flex-shrink: 0;
}
.plot-modal-body { flex: 1; min-height: 0; overflow: auto; }
.plot-modal-body .js-plotly-plot { width: 100% !important; height: 100% !important; min-height: 400px; }
/* ── Confusion matrix ─────────────────────────────────────────────────── */
.confusion-matrix {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    max-width: 340px;
    margin: 20px auto;
}
.cm-cell { background: var(--surface-alt); padding: 20px; text-align: center; border-radius: 8px; }
.cm-cell.tp { border-left: 4px solid var(--positive); }
.cm-cell.tn { border-left: 4px solid var(--neutral); }
.cm-cell.fp { border-left: 4px solid var(--negative); }
.cm-cell.fn { border-left: 4px solid var(--warning); }
.cm-cell .value { font-size: 2em; font-weight: bold; color: var(--text); }
.cm-cell .label { font-size: 0.8em; color: var(--text-muted); }
/* ── Calibration info ─────────────────────────────────────────────────── */
.calibration-info {
    background: var(--surface-alt);
    padding: 15px 20px;
    border-radius: 8px;
    border-left: 4px solid #17a2b8;
    margin-top: 10px;
}
.calibration-info p { margin: 4px 0; color: var(--text); font-size: 0.95em; }
/* ── Model info panel ─────────────────────────────────────────────────── */
.model-info-cards {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 16px;
}
.model-info-card {
    background: var(--surface-alt);
    border-radius: 8px;
    padding: 12px 16px;
    border-left: 3px solid var(--secondary);
    min-width: 120px;
}
.model-info-card .label { font-size: 0.75em; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.5px; }
.model-info-card .value { font-size: 1.1em; font-weight: 600; color: var(--text); word-break: break-word; }
details.hyperparams-details { margin-top: 12px; }
details.hyperparams-details summary {
    cursor: pointer;
    color: var(--primary);
    font-size: 0.9em;
    font-weight: 600;
    padding: 6px 0;
    user-select: none;
}
.hyperparams-table { width: 100%; border-collapse: collapse; font-size: 0.88em; margin-top: 8px; }
.hyperparams-table th {
    background: var(--surface-alt);
    padding: 8px 12px;
    text-align: left;
    color: var(--text-muted);
    font-weight: 600;
    font-size: 0.8em;
    text-transform: uppercase;
    border-bottom: 1px solid var(--border);
}
.hyperparams-table td { padding: 7px 12px; border-bottom: 1px solid var(--border); color: var(--text); }
.hyperparams-table tr:last-child td { border-bottom: none; }
/* ── Threshold sweep ──────────────────────────────────────────────────── */
.threshold-summary { margin-top: 16px; }
.threshold-summary table { width: 100%; border-collapse: collapse; font-size: 0.88em; }
.threshold-summary th {
    background: var(--surface-alt);
    padding: 8px 12px;
    text-align: left;
    color: var(--text-muted);
    font-size: 0.8em;
    text-transform: uppercase;
    border-bottom: 1px solid var(--border);
}
.threshold-summary td { padding: 7px 12px; border-bottom: 1px solid var(--border); color: var(--text); }
.threshold-summary tr.optimal-row { background: rgba(102,126,234,0.08); font-weight: 600; }
/* ── Segment metrics table ────────────────────────────────────────────── */
.segment-table-wrap { overflow-x: auto; }
.segment-table { width: 100%; border-collapse: collapse; font-size: 0.88em; }
.segment-table th {
    background: var(--surface-alt);
    padding: 9px 14px;
    text-align: left;
    color: var(--text-muted);
    font-size: 0.8em;
    text-transform: uppercase;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
}
.segment-table td { padding: 8px 14px; border-bottom: 1px solid var(--border); text-align: right; }
.segment-table td:first-child { text-align: left; color: var(--text); font-weight: 500; }
.segment-table tr:last-child td { border-bottom: none; }
.heat-high { color: var(--positive); font-weight: 700; }
.heat-mid  { color: var(--warning);  font-weight: 600; }
.heat-low  { color: var(--negative); font-weight: 700; }
/* ── Footer ───────────────────────────────────────────────────────────── */
.footer { text-align: center; padding: 20px; color: var(--text-faint); font-size: 0.9em; }
"""

INDEX_CSS = SHARED_CSS + """\
/* ── Base ─────────────────────────────────────────────────────────────── */
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    line-height: 1.6;
    color: var(--text);
    background-color: var(--bg);
    padding: 20px;
}
/* ── Header ───────────────────────────────────────────────────────────── */
.header {
    background: var(--header-gradient);
    color: white;
    padding: 30px 35px;
    border-radius: 10px;
    margin-bottom: 30px;
    box-shadow: 0 4px 6px var(--shadow);
    position: relative;
}
.header h1 { font-size: 2em; margin-bottom: 5px; }
.header p { opacity: 0.85; font-size: 0.95em; }
/* ── Summary cards ────────────────────────────────────────────────────── */
.summary-bar { display: flex; gap: 15px; margin-bottom: 25px; flex-wrap: wrap; }
.summary-card {
    background: var(--surface);
    padding: 15px 20px;
    border-radius: 8px;
    box-shadow: 0 2px 4px var(--shadow-sm);
    border-left: 4px solid var(--primary);
    min-width: 140px;
}
.summary-card .value { font-size: 1.8em; font-weight: bold; color: var(--primary); }
.summary-card .label { font-size: 0.8em; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.5px; }
/* ── Search & filter ──────────────────────────────────────────────────── */
.search-row {
    display: flex;
    gap: 10px;
    padding: 14px 20px;
    flex-wrap: wrap;
    align-items: center;
    border-bottom: 1px solid var(--border);
}
.search-bar {
    flex: 1;
    min-width: 180px;
    padding: 8px 12px;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 0.9em;
    background: var(--surface-alt);
    color: var(--text);
}
.search-bar:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 2px rgba(102,126,234,0.2); }
.filter-dropdown {
    padding: 8px 12px;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 0.9em;
    background: var(--surface-alt);
    color: var(--text);
    cursor: pointer;
}
.filter-dropdown:focus { outline: none; border-color: var(--primary); }
/* ── Section ──────────────────────────────────────────────────────────── */
.section {
    background: var(--surface);
    border-radius: 10px;
    box-shadow: 0 2px 4px var(--shadow-sm);
    overflow: hidden;
    margin-bottom: 20px;
}
.section-header {
    padding: 18px 25px;
    border-bottom: 2px solid var(--primary);
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.section-header h2 { color: var(--primary); font-size: 1.2em; }
/* ── Table ────────────────────────────────────────────────────────────── */
table { width: 100%; border-collapse: collapse; font-size: 0.92em; }
thead th {
    background: var(--surface-alt);
    padding: 12px 16px;
    text-align: left;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    font-size: 0.78em;
    letter-spacing: 0.5px;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
}
thead th.no-sort { cursor: default; }
thead th:not(.no-sort):hover { background: var(--border); color: var(--text); }
thead th.sorted-asc::after { content: " \25B2"; color: var(--primary); }
thead th.sorted-desc::after { content: " \25BC"; color: var(--primary); }
tbody tr { border-bottom: 1px solid var(--border); transition: background 0.15s; }
tbody tr:hover { background: var(--surface-alt); }
tbody tr.selected { background: rgba(102,126,234,0.08) !important; }
tbody tr.hidden { display: none; }
tbody tr:last-child { border-bottom: none; }
td { padding: 12px 16px; vertical-align: middle; }
td.run-name {
    font-family: 'SF Mono', 'Fira Code', 'Courier New', monospace;
    font-size: 0.88em;
    color: var(--text);
    font-weight: 500;
}
td.metric { text-align: right; font-variant-numeric: tabular-nums; font-weight: 500; }
td.metric.high { color: var(--positive); }
td.metric.mid { color: var(--warning); }
td.metric.low { color: var(--negative); }
td.metric.na { color: var(--text-faint); }
/* ── Mini bar chart (CSS-only) ────────────────────────────────────────── */
.mini-bar-wrap { display: flex; align-items: center; gap: 6px; }
.mini-bar {
    height: 8px;
    border-radius: 4px;
    background: var(--primary);
    opacity: 0.7;
    min-width: 2px;
    transition: width 0.3s;
}
/* ── Delta column ─────────────────────────────────────────────────────── */
.delta-positive { color: var(--positive); font-weight: 600; }
.delta-negative { color: var(--negative); font-weight: 600; }
/* ── Report link ──────────────────────────────────────────────────────── */
.report-link {
    display: inline-block;
    padding: 5px 12px;
    background: var(--primary);
    color: white;
    text-decoration: none;
    border-radius: 5px;
    font-size: 0.82em;
    font-weight: 500;
    transition: background 0.15s;
}
.report-link:hover { background: var(--primary-dark); }
.no-runs { padding: 50px; text-align: center; color: var(--text-faint); font-size: 1.05em; }
/* ── Footer ───────────────────────────────────────────────────────────── */
.footer { text-align: center; padding: 20px; color: var(--text-faint); font-size: 0.85em; }
/* ── Row select ───────────────────────────────────────────────────────── */
.row-select { cursor: pointer; width: 15px; height: 15px; accent-color: var(--primary); }
/* ── Comparison panel ─────────────────────────────────────────────────── */
#comparison-panel {
    display: none;
    background: var(--surface);
    border-radius: 10px;
    box-shadow: 0 2px 8px var(--shadow);
    overflow: hidden;
    margin-bottom: 20px;
    border: 2px solid var(--primary);
}
#comparison-panel .section-header {
    background: var(--header-gradient);
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
    background: var(--surface-alt);
    font-weight: 600;
    color: var(--text-muted);
    font-size: 0.82em;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
/* ── Compare bar (fixed bottom) ───────────────────────────────────────── */
.compare-bar {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--primary);
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
    color: var(--primary);
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

# Expose the dark-toggle JS snippet for use in templates
DARK_TOGGLE_JS = _DARK_TOGGLE_JS
