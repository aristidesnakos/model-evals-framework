"""
EvalPulse Dashboard — local web UI for browsing evaluation results.

Uses only Python stdlib. Serves a single-page app that reads JSON
reports from the reports/ directory via a small REST API.
"""

import json
import re
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path


def start_dashboard(port: int, reports_dir: Path):
    """Start the dashboard server and open the browser."""
    reports_dir.mkdir(exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                self._serve_html()
            elif self.path == "/api/reports":
                self._serve_report_list()
            elif self.path.startswith("/api/reports/"):
                filename = self.path[len("/api/reports/"):]
                self._serve_report(filename)
            else:
                self._respond(404, {"error": "Not found"})

        def _serve_html(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())

        def _serve_report_list(self):
            reports = []
            for f in sorted(reports_dir.glob("*.json"), reverse=True):
                if f.name.endswith("_classification.json"):
                    continue  # sidecar scoring data, not a report — see generate_demo_data.py's same exclusion
                try:
                    data = json.loads(f.read_text())
                    model_scores = []
                    for r in data.get("results", []):
                        scores = [tr["avg_score"] for tr in r.get("test_results", []) if isinstance(tr.get("avg_score"), (int, float)) and tr["avg_score"] > 0]
                        if scores:
                            model_scores.append({"name": r["model_name"], "avg": round(sum(scores) / len(scores), 1)})
                    model_scores.sort(key=lambda x: x["avg"], reverse=True)
                    model_ids = {r.get("model_id") for r in data.get("results", []) if r.get("model_id")}
                    reports.append({
                        "filename": f.name,
                        "run_id": data.get("run_id", ""),
                        "suite_name": data.get("suite_name", ""),
                        "eval_type": data.get("eval_type", "quality"),
                        "model_count": len(model_ids) if model_ids else len(data.get("results", [])),
                        "top_model": model_scores[0] if model_scores else None,
                        "score_range": [model_scores[-1]["avg"], model_scores[0]["avg"]] if model_scores else None,
                    })
                except (json.JSONDecodeError, KeyError):
                    continue
            self._respond(200, reports)

        def _serve_report(self, filename: str):
            safe = re.sub(r"[^a-zA-Z0-9_\-.]", "", filename)
            if not safe.endswith(".json"):
                safe += ".json"
            path = reports_dir / safe
            if not path.exists():
                self._respond(404, {"error": f"Report not found: {safe}"})
                return
            try:
                data = json.loads(path.read_text())
                self._respond(200, data)
            except json.JSONDecodeError:
                self._respond(500, {"error": "Invalid JSON in report file"})

        def _respond(self, status: int, data):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data, default=str).encode())

        def log_message(self, format, *args):
            pass  # Suppress request logging

    server = HTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"EvalPulse Dashboard running at {url}")
    print("Press Ctrl+C to stop.\n")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
        server.server_close()


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EvalPulse Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
:root {
  --bg: #f1f5f9; --surface: #ffffff; --text: #1e293b; --muted: #64748b;
  --border: #e2e8f0; --accent: #3b82f6; --accent-light: #eff6ff;
  --green: #22c55e; --amber: #f59e0b; --red: #ef4444;
  --radius: 8px; --shadow: 0 1px 3px rgba(0,0,0,0.08);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); font-size: 14px; line-height: 1.5; }
header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 16px 24px; display: flex; align-items: center; gap: 16px; position: sticky; top: 0; z-index: 10; }
header h1 { font-size: 18px; font-weight: 700; }
header nav { display: flex; gap: 8px; margin-left: auto; }
header nav a, header nav button { padding: 6px 14px; border-radius: 6px; text-decoration: none; color: var(--muted); font-size: 13px; font-weight: 500; cursor: pointer; border: 1px solid var(--border); background: var(--surface); transition: all 0.15s; }
header nav a:hover, header nav button:hover { color: var(--accent); border-color: var(--accent); }
header nav a.active { color: var(--accent); background: var(--accent-light); border-color: var(--accent); }
#app { max-width: 1200px; margin: 24px auto; padding: 0 24px; }

/* Cards */
.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; margin-bottom: 16px; box-shadow: var(--shadow); }
.card-primary { border-left: 3px solid var(--accent); }
.card h2 { font-size: 15px; font-weight: 600; }

/* Section header: title left, inline legend right — same visual row */
.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; flex-wrap: wrap; gap: 8px; }
.section-header h2 { margin-bottom: 0; }

/* Inline legend — appears once, anchored to the section it describes */
.inline-legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 12px; color: var(--muted); align-items: center; }
.inline-legend .key-item { display: flex; align-items: center; gap: 5px; }
.inline-legend .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.inline-legend .dot-green { background: var(--green); }
.inline-legend .dot-amber { background: var(--amber); }
.inline-legend .dot-red { background: var(--red); }
.inline-legend .key-divider { color: var(--border); }

/* Hero stats — focal point KPIs at the top of a run */
.hero-stats { display: flex; margin: 16px 0 14px; border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
.hero-stat { flex: 1; padding: 14px 16px; text-align: center; border-right: 1px solid var(--border); }
.hero-stat:last-child { border-right: none; }
.hero-num { display: block; font-size: 26px; font-weight: 700; line-height: 1.1; font-variant-numeric: tabular-nums; }
.hero-label { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted); margin-top: 3px; }

/* Scale note — "(1–10)" in a column header, once per table */
.scale-note { font-size: 10px; font-weight: 400; color: var(--muted); letter-spacing: 0; text-transform: none; }

/* Min–max range shown under avg score cell */
.score-range-hint { display: block; font-size: 11px; font-weight: 400; color: var(--muted); margin-top: 1px; }

/* Tables */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; padding: 8px 10px; border-bottom: 2px solid var(--border); font-weight: 600; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; }
td { padding: 8px 10px; border-bottom: 1px solid var(--border); vertical-align: middle; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--accent-light); }
.score { font-weight: 600; font-variant-numeric: tabular-nums; }
.score-high { color: var(--green); }
.score-mid { color: var(--amber); }
.score-low { color: var(--red); }

/* Heatmap cells — colored backgrounds for dimension tables */
.heatmap-cell { padding: 3px 7px; border-radius: 4px; font-weight: 600; font-size: 12px; display: inline-block; min-width: 34px; text-align: center; }

/* Category group dividers inside per-test-case section */
.category-group { display: flex; align-items: center; gap: 10px; padding: 12px 0 6px; margin-top: 4px; border-top: 1px solid var(--border); }
.category-group:first-child { border-top: none; padding-top: 4px; }
.category-group-stats { font-size: 12px; color: var(--muted); }

/* Badges */
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
.badge-suite { background: #ede9fe; color: #7c3aed; }
.badge-cat { background: #e0f2fe; color: #0284c7; }
.badge-quality { background: #e0f2fe; color: #0284c7; }
.badge-safety { background: #fee2e2; color: #b91c1c; }
.badge-agentic { background: #dcfce7; color: #15803d; }

/* Eval-type filter pills — index page */
.type-filter { display: flex; gap: 8px; margin-bottom: 16px; }
.type-filter button { padding: 6px 14px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface); color: var(--muted); font-size: 13px; font-weight: 500; cursor: pointer; }
.type-filter button:hover { border-color: var(--accent); color: var(--accent); }
.type-filter button.active { background: var(--accent-light); border-color: var(--accent); color: var(--accent); }

/* Meta row */
.meta { display: flex; gap: 20px; flex-wrap: wrap; font-size: 13px; color: var(--muted); }
.meta span { display: flex; align-items: center; gap: 4px; }
.meta strong { color: var(--text); }

/* Score range bar — index table */
.range-bar-wrap { display: flex; align-items: center; gap: 8px; }
.range-bar-track { flex: 1; height: 5px; background: var(--border); border-radius: 3px; min-width: 56px; position: relative; overflow: hidden; }
.range-bar-fill { position: absolute; top: 0; height: 100%; border-radius: 3px; }
.range-text { font-size: 12px; color: var(--muted); white-space: nowrap; font-variant-numeric: tabular-nums; }

/* Strongest/weakest dimension callout */
.dim-callout { font-size: 12px; color: var(--muted); margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border); }
.dim-callout strong { color: var(--text); }

/* Winner badge in comparison view */
.winner-badge { display: inline-block; padding: 1px 7px; border-radius: 10px; font-size: 11px; font-weight: 600; background: #dcfce7; color: #166534; margin-left: 6px; vertical-align: middle; }

/* Charts */
.chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.chart-container { position: relative; height: 280px; }

/* Collapsibles */
details { margin-bottom: 4px; }
details summary { padding: 10px 12px; cursor: pointer; border-radius: 6px; font-weight: 500; display: flex; justify-content: space-between; align-items: center; background: var(--bg); }
details summary:hover { background: var(--accent-light); }
details[open] summary { border-bottom: 1px solid var(--border); border-radius: 6px 6px 0 0; }
details .detail-content { padding: 8px 0 4px; }
.summary-right { display: flex; align-items: center; gap: 12px; font-size: 12px; color: var(--muted); flex-shrink: 0; }

/* Empty state */
.empty-state { text-align: center; padding: 60px 20px; color: var(--muted); }
.empty-state h2 { font-size: 20px; color: var(--text); margin-bottom: 8px; }

/* Compare button */
.btn-compare { background: var(--accent); color: #fff; border: none; padding: 6px 14px; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; opacity: 0.5; pointer-events: none; }
.btn-compare.enabled { opacity: 1; pointer-events: auto; }
.btn-compare.enabled:hover { background: #2563eb; }
input[type=checkbox] { accent-color: var(--accent); }

/* Delta colors */
.delta-up { color: var(--green); font-weight: 600; }
.delta-down { color: var(--red); font-weight: 600; }
.delta-flat { color: var(--muted); }

@media (max-width: 768px) {
  .chart-row { grid-template-columns: 1fr; }
  .hero-stats { flex-wrap: wrap; }
  .hero-stat { min-width: 50%; }
}
</style>
</head>
<body>
<header>
  <h1>EvalPulse</h1>
  <nav>
    <a href="#/" class="nav-link active" data-route="index">Runs</a>
    <button class="btn-compare" id="compareBtn" onclick="goCompare()">Compare Selected</button>
  </nav>
</header>
<div id="app"></div>

<script>
const cache = {};
const selected = new Set();

async function fetchList() {
  if (cache._list) return cache._list;
  const r = await fetch('/api/reports');
  cache._list = await r.json();
  return cache._list;
}

async function fetchReport(filename) {
  if (cache[filename]) return cache[filename];
  const r = await fetch('/api/reports/' + filename);
  cache[filename] = await r.json();
  return cache[filename];
}

function scoreClass(v) { return v >= 7 ? 'score-high' : v >= 5 ? 'score-mid' : 'score-low'; }
function evalTypeBadge(t) { return `<span class="badge badge-${t}">${t}</span>`; }
let typeFilter = 'all';
function fmtDate(runId) {
  if (!runId || runId.length < 15) return runId || '';
  return runId.slice(0,4)+'-'+runId.slice(4,6)+'-'+runId.slice(6,8)+' '+runId.slice(9,11)+':'+runId.slice(11,13)+' UTC';
}
function stdColor(v) { return v < 0.5 ? 'var(--green)' : v < 1.0 ? 'var(--amber)' : 'var(--red)'; }
function heatBg(v) { return v >= 7 ? '#dcfce7' : v >= 5 ? '#fef9c3' : '#fee2e2'; }
function heatFg(v) { return v >= 7 ? '#166534' : v >= 5 ? '#854d0e' : '#991b1b'; }

const COLORS = ['#3b82f6','#22c55e','#f59e0b','#ef4444','#8b5cf6','#ec4899','#14b8a6','#f97316'];
const DIMS    = ['completeness','accuracy','format','domain_relevance','clarity'];
const DLABELS = ['Complete','Accuracy','Format','Domain','Clarity'];

function updateNav(route) {
  document.querySelectorAll('.nav-link').forEach(a => {
    a.classList.toggle('active', a.dataset.route === route);
  });
}

function updateCompareBtn() {
  const btn = document.getElementById('compareBtn');
  btn.classList.toggle('enabled', selected.size >= 2);
  btn.textContent = selected.size >= 2 ? `Compare (${selected.size})` : 'Compare Selected';
}

function goCompare() {
  if (selected.size < 2) return;
  location.hash = '#/compare?' + [...selected].map(f => 'id=' + f).join('&');
}

// Per-dimension averages across all runs for a model result
function dimAverages(mr) {
  const out = {};
  DIMS.forEach(d => {
    const vals = mr.test_results.flatMap(t => t.runs).filter(r => r.scores && r.scores[d]);
    out[d] = vals.length ? +(vals.map(r => r.scores[d]).reduce((a,b)=>a+b,0)/vals.length).toFixed(1) : 0;
  });
  return out;
}

function modelSummaries(data) {
  return data.results.map(mr => {
    const scores = mr.test_results.filter(t => t.avg_score > 0).map(t => t.avg_score);
    const lats = []; let tokens = 0; let cost = 0;
    mr.test_results.forEach(tr => tr.runs.forEach(r => {
      if (r.latency) lats.push(r.latency);
      tokens += (r.tokens?.input||0) + (r.tokens?.output||0);
      cost += r.cost || 0;
    }));
    const stds = mr.test_results.filter(t => t.std_dev > 0).map(t => t.std_dev);
    return {
      id: mr.model_id, name: mr.model_name,
      avg: scores.length ? +(scores.reduce((a,b)=>a+b,0)/scores.length).toFixed(1) : 0,
      min: scores.length ? +Math.min(...scores).toFixed(1) : 0,
      max: scores.length ? +Math.max(...scores).toFixed(1) : 0,
      std: stds.length ? +(stds.reduce((a,b)=>a+b,0)/stds.length).toFixed(2) : 0,
      lat: lats.length ? +(lats.reduce((a,b)=>a+b,0)/lats.length).toFixed(1) : 0,
      cost: +cost.toFixed(4), tokens, errors: mr.errors,
      dims: dimAverages(mr)
    };
  }).sort((a,b) => b.avg - a.avg);
}

function fmtCost(v) {
  if (v >= 0.01) return '$' + v.toFixed(2);
  if (v >= 0.001) return '$' + v.toFixed(3);
  return '$' + v.toFixed(4);
}

// Group test cases by category → Map<category, tc[]>
function groupByCategory(testCases) {
  const map = new Map();
  testCases.forEach(tc => {
    const cat = tc.category || 'general';
    if (!map.has(cat)) map.set(cat, []);
    map.get(cat).push(tc);
  });
  return map;
}

// --- RENDERERS ---

async function renderIndex() {
  updateNav('index');
  const app = document.getElementById('app');
  const reports = await fetchList();

  if (!reports.length) {
    app.innerHTML = '<div class="empty-state"><h2>No reports yet</h2><p>Run an evaluation first:<br><code>python src/main.py --run-eval</code></p></div>';
    return;
  }

  const uniqueSuites = new Set(reports.map(r => r.suite_name)).size;
  const totalModelEvals = reports.reduce((s, r) => s + r.model_count, 0);
  const typeCounts = { quality: 0, safety: 0, agentic: 0 };
  reports.forEach(r => { typeCounts[r.eval_type] = (typeCounts[r.eval_type] || 0) + 1; });

  const visible = typeFilter === 'all' ? reports : reports.filter(r => r.eval_type === typeFilter);

  const rows = visible.map(r => {
    const range = r.score_range ? `<div class="range-bar-wrap">
          <div class="range-bar-track"><div class="range-bar-fill" style="left:${(r.score_range[0]/10*100).toFixed(1)}%;width:${((r.score_range[1]-r.score_range[0])/10*100).toFixed(1)}%;background:${r.score_range[1]>=7?'var(--green)':r.score_range[1]>=5?'var(--amber)':'var(--red)'}"></div></div>
          <span class="range-text">${r.score_range[0]}–${r.score_range[1]}</span>
        </div>` : '—';
    return `<tr>
      <td><input type="checkbox" data-file="${r.filename}" onchange="toggleSelect(this)" ${selected.has(r.filename)?'checked':''}></td>
      <td><a href="#/run/${r.filename}" style="color:var(--accent);text-decoration:none;font-weight:500">${fmtDate(r.run_id)}</a></td>
      <td>${evalTypeBadge(r.eval_type)}</td>
      <td><span class="badge badge-suite">${r.suite_name}</span></td>
      <td style="text-align:center">${r.model_count}</td>
      <td>${r.top_model ? `<span class="score ${scoreClass(r.top_model.avg)}">${r.top_model.avg}</span> <span style="color:var(--muted);font-size:12px">${r.top_model.name}</span>` : '—'}</td>
      <td>${range}</td>
    </tr>`;
  }).join('');

  app.innerHTML = `
  <div class="hero-stats">
    <div class="hero-stat"><span class="hero-num">${reports.length}</span><span class="hero-label">Runs</span></div>
    <div class="hero-stat"><span class="hero-num">${uniqueSuites}</span><span class="hero-label">Suites</span></div>
    <div class="hero-stat"><span class="hero-num">${totalModelEvals}</span><span class="hero-label">Model Evaluations</span></div>
  </div>
  <div class="type-filter">
    <button class="${typeFilter==='all'?'active':''}" onclick="setTypeFilter('all')">All (${reports.length})</button>
    <button class="${typeFilter==='quality'?'active':''}" onclick="setTypeFilter('quality')">Quality (${typeCounts.quality||0})</button>
    <button class="${typeFilter==='safety'?'active':''}" onclick="setTypeFilter('safety')">Safety (${typeCounts.safety||0})</button>
    <button class="${typeFilter==='agentic'?'active':''}" onclick="setTypeFilter('agentic')">Agentic (${typeCounts.agentic||0})</button>
  </div>
  <div class="card">
    <div class="section-header">
      <h2>Evaluation Runs</h2>
      <div class="inline-legend">Quality: 1–10 dual LLM judges · Safety: deploy-gate tiers · Agentic: grounded success rate</div>
    </div>
    <table><thead><tr>
      <th width="30"></th>
      <th>Date</th><th>Type</th><th>Suite</th>
      <th style="text-align:center">Models</th>
      <th>Leader <span class="scale-note">(1–10)</span></th>
      <th>Score Range</th>
    </tr></thead><tbody>${rows}</tbody></table>
  </div>`;
}

function setTypeFilter(t) { typeFilter = t; renderIndex(); }

function toggleSelect(cb) {
  if (cb.checked) selected.add(cb.dataset.file); else selected.delete(cb.dataset.file);
  updateCompareBtn();
}

async function renderRun(filename) {
  updateNav('');
  const app = document.getElementById('app');
  const data = await fetchReport(filename);
  if (data.error) { app.innerHTML = `<div class="card"><p>${data.error}</p></div>`; return; }
  if (data.eval_type === 'safety') { renderSafetyRun(data); return; }
  if (data.eval_type === 'agentic') { renderAgenticRun(data); return; }

  const summaries = modelSummaries(data);
  const testCases = data.results.length > 0 ? data.results[0].test_results : [];
  const topScore  = summaries.length ? summaries[0].avg : 0;
  const avgStd    = summaries.length
    ? +(summaries.map(m=>m.std).reduce((a,b)=>a+b,0)/summaries.length).toFixed(2) : 0;

  // --- 1. Run header: meta + hero stats + legend (all in one card) ---
  let html = `<div class="card">
    <div class="meta">
      <span><strong>Suite</strong> <span class="badge badge-suite">${data.suite_name}</span></span>
      <span><strong>Date</strong> ${fmtDate(data.run_id)}</span>
      <span><strong>Runs/test</strong> ${data.runs_per_test}</span>
      <span><strong>Judges</strong> ${(data.judge_models||[]).join(', ')}</span>
    </div>
    <div class="hero-stats">
      <div class="hero-stat"><span class="hero-num score ${scoreClass(topScore)}">${topScore}</span><span class="hero-label">Top Score</span></div>
      <div class="hero-stat"><span class="hero-num">${summaries.length}</span><span class="hero-label">Models</span></div>
      <div class="hero-stat"><span class="hero-num">${testCases.length}</span><span class="hero-label">Test Cases</span></div>
      <div class="hero-stat"><span class="hero-num" style="color:${stdColor(avgStd)}">${avgStd}</span><span class="hero-label">Avg Consistency</span></div>
    </div>
    <div class="inline-legend">
      <span class="key-item"><span class="dot dot-green"></span>7–10 Strong</span>
      <span class="key-item"><span class="dot dot-amber"></span>5–6.9 Moderate</span>
      <span class="key-item"><span class="dot dot-red"></span>&lt;5 Weak</span>
      <span class="key-divider">·</span>
      <span>Std Dev: lower = more consistent across runs</span>
    </div>
  </div>`;

  // --- 2. Model leaderboard (primary card) ---
  html += `<div class="card card-primary">
    <div class="section-header"><h2>Model Leaderboard</h2></div>
    <div class="chart-container" style="height:${Math.max(180, summaries.length*52)}px"><canvas id="leaderboard"></canvas></div>
    <table style="margin-top:16px"><thead><tr>
      <th>#</th><th>Model</th>
      <th>Score <span class="scale-note">(1–10)</span></th>
      <th>Consistency</th><th>Avg Latency</th><th>Cost</th><th>Errors</th>
    </tr></thead><tbody>`;
  summaries.forEach((m, i) => {
    html += `<tr>
      <td style="color:var(--muted);font-weight:500">${i+1}</td>
      <td style="font-weight:500">${m.name}</td>
      <td><span class="score ${scoreClass(m.avg)}">${m.avg}</span><span class="score-range-hint">${m.min}–${m.max} range</span></td>
      <td style="color:${stdColor(m.std)};font-weight:600">${m.std}</td>
      <td>${m.lat}s</td>
      <td>${fmtCost(m.cost)}</td>
      <td>${m.errors > 0 ? `<span style="color:var(--red);font-weight:600">${m.errors}</span>` : '0'}</td>
    </tr>`;
  });
  html += '</tbody></table></div>';

  // --- Cost vs Intelligence scatter ---
  html += `<div class="card card-primary">
    <div class="section-header">
      <h2>Cost vs Intelligence</h2>
      <div class="inline-legend">
        <span class="key-item"><span class="dot dot-green"></span>7–10 Strong</span>
        <span class="key-item"><span class="dot dot-amber"></span>5–6.9 Moderate</span>
        <span class="key-item"><span class="dot dot-red"></span>&lt;5 Weak</span>
      </div>
    </div>
    <div class="chart-container" style="height:340px"><canvas id="cost-scatter"></canvas></div>
    <p style="font-size:12px;color:var(--muted);margin-top:6px;text-align:center">Higher is smarter · Left is cheaper · <span style="color:var(--green);font-weight:600">Top-left wins</span></p>
  </div>`;

  // --- 3. Radar + Reliability side by side ---
  html += `<div class="chart-row">
    <div class="card">
      <div class="section-header"><h2>Dimension Profiles</h2></div>
      <div class="chart-container"><canvas id="radar"></canvas></div>
    </div>
    <div class="card">
      <div class="section-header">
        <h2>Reliability</h2>
        <div class="inline-legend">
          <span class="key-item"><span class="dot dot-green"></span>&lt;0.5 Consistent</span>
          <span class="key-item"><span class="dot dot-amber"></span>0.5–1.0 Variable</span>
          <span class="key-item"><span class="dot dot-red"></span>≥1.0 Unstable</span>
        </div>
      </div>
      <div class="chart-container"><canvas id="reliability"></canvas></div>
    </div>
  </div>`;

  // --- 4. Dimension heatmap (full-width) ---
  // Cross-model dimension averages for strongest/weakest callout
  const allDimAvgs = {};
  DIMS.forEach(d => {
    const vals = summaries.map(m => m.dims[d]).filter(v => v > 0);
    allDimAvgs[d] = vals.length ? +(vals.reduce((a,b)=>a+b,0)/vals.length).toFixed(1) : 0;
  });
  const sortedByAvg = [...DIMS].sort((a,b) => allDimAvgs[b] - allDimAvgs[a]);
  const strongest = sortedByAvg[0], weakest = sortedByAvg[sortedByAvg.length-1];

  html += `<div class="card"><div class="section-header"><h2>Dimension Breakdown</h2></div>
    <table><thead><tr>
      <th>Model</th>
      ${DLABELS.map(l => `<th style="text-align:center">${l}</th>`).join('')}
    </tr></thead><tbody>`;
  summaries.forEach(m => {
    html += `<tr><td style="font-weight:500">${m.name}</td>`;
    DIMS.forEach(d => {
      const v = m.dims[d];
      html += `<td style="text-align:center"><span class="heatmap-cell" style="background:${heatBg(v)};color:${heatFg(v)}">${v}</span></td>`;
    });
    html += '</tr>';
  });
  html += `</tbody></table>
    <p class="dim-callout"><strong>Strongest:</strong> ${strongest.replace('_',' ')} (${allDimAvgs[strongest]} avg)&emsp;<strong>Weakest:</strong> ${weakest.replace('_',' ')} (${allDimAvgs[weakest]} avg)</p>
  </div>`;

  // --- 5. Per-test-case results, grouped by category ---
  html += '<div class="card"><h2 style="margin-bottom:12px">Per-Test-Case Results</h2>';
  if (data.results.length > 0) {
    const byCategory = groupByCategory(testCases);
    byCategory.forEach((catTcs, category) => {
      // Category-level avg score
      const catScores = [];
      catTcs.forEach(tc => {
        data.results.forEach(mr => {
          const m = mr.test_results.find(t => t.test_case_id === tc.test_case_id);
          if (m && m.avg_score > 0) catScores.push(m.avg_score);
        });
      });
      const catAvg = catScores.length
        ? +(catScores.reduce((a,b)=>a+b,0)/catScores.length).toFixed(1) : 0;

      html += `<div class="category-group">
        <span class="badge badge-cat">${category}</span>
        <span class="category-group-stats">
          <span class="score ${scoreClass(catAvg)}" style="font-weight:600">${catAvg}</span>
          avg · ${catTcs.length} test${catTcs.length > 1 ? 's' : ''}
        </span>
      </div>`;

      catTcs.forEach(tc => {
        const tcRows = [];
        data.results.forEach(mr => {
          const match = mr.test_results.find(t => t.test_case_id === tc.test_case_id);
          if (!match) return;
          const valid = match.runs.filter(r => r.scores);
          const dims = {};
          DIMS.forEach(d => {
            dims[d] = valid.length
              ? +(valid.map(r => r.scores[d]||0).reduce((a,b)=>a+b,0)/valid.length).toFixed(1) : 0;
          });
          tcRows.push({ name: mr.model_name, avg: match.avg_score, std: match.std_dev, ...dims });
        });
        tcRows.sort((a,b) => b.avg - a.avg);
        const passCount = tcRows.filter(r => r.avg >= 7).length;

        const tcPrompt = tc.prompt || '';
        const tcRef = tc.reference_answer || '';
        html += `<details><summary>
          <span style="font-weight:500">${tc.test_case_name}</span>
          <span class="summary-right">
            <span>${passCount}/${tcRows.length} scored 7+</span>
            <span class="score ${scoreClass(tcRows[0]?.avg||0)}">${tcRows[0]?.avg||0}</span>
          </span>
        </summary>
        <div class="detail-content">`;
        if (tcPrompt) html += `<div style="margin-bottom:10px;padding:10px 12px;background:var(--bg);border-radius:6px;font-size:13px"><strong>Prompt:</strong> ${tcPrompt}</div>`;
        if (tcRef) html += `<div style="margin-bottom:10px;padding:10px 12px;background:var(--bg);border-radius:6px;font-size:13px"><strong>Expected:</strong> ${tcRef}</div>`;
        html += `<table><thead><tr>
          <th>Model</th>
          <th>Score <span class="scale-note">(1–10)</span></th>
          <th>Std Dev</th>
          ${DLABELS.map(l => `<th style="text-align:center">${l}</th>`).join('')}
        </tr></thead><tbody>`;
        tcRows.forEach(r => {
          html += `<tr>
            <td style="font-weight:500">${r.name}</td>
            <td><span class="score ${scoreClass(r.avg)}">${r.avg}</span></td>
            <td style="color:${stdColor(r.std)};font-weight:600">${r.std}</td>
            ${DIMS.map(d => `<td style="text-align:center"><span class="heatmap-cell" style="background:${heatBg(r[d])};color:${heatFg(r[d])}">${r[d]}</span></td>`).join('')}
          </tr>`;
        });
        html += '</tbody></table></div></details>';
      });
    });
  }
  html += '</div>';

  app.innerHTML = html;

  // Render charts
  if (summaries.length > 0) {
    new Chart(document.getElementById('leaderboard'), {
      type: 'bar',
      options: {
        indexAxis: 'y', responsive: true, maintainAspectRatio: false,
        scales: {
          x: { min: 0, max: 10, grid: { color: '#f1f5f9' }, ticks: { stepSize: 2 } },
          y: { grid: { display: false } }
        },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: ctx => `${ctx.raw}/10  (range ${summaries[ctx.dataIndex].min}–${summaries[ctx.dataIndex].max})` } }
        }
      },
      data: {
        labels: summaries.map(m => m.name),
        datasets: [{ data: summaries.map(m => m.avg),
          backgroundColor: summaries.map(m => m.avg>=7?'#22c55e':m.avg>=5?'#f59e0b':'#ef4444'),
          borderRadius: 4, barThickness: 28 }]
      }
    });

    const radarDS = data.results.map((mr, i) => {
      const vals = DIMS.map(d => {
        const valid = mr.test_results.flatMap(t=>t.runs).filter(r=>r.scores);
        return valid.length ? +(valid.map(r=>r.scores[d]||0).reduce((a,b)=>a+b,0)/valid.length).toFixed(1) : 0;
      });
      return { label: mr.model_name, data: vals,
        borderColor: COLORS[i%COLORS.length],
        backgroundColor: COLORS[i%COLORS.length]+'22',
        pointRadius: 3, borderWidth: 2 };
    });
    new Chart(document.getElementById('radar'), {
      type: 'radar',
      data: { labels: DLABELS, datasets: radarDS },
      options: {
        responsive: true, maintainAspectRatio: false,
        scales: { r: { min: 0, max: 10, ticks: { stepSize: 2, font: { size: 10 } }, pointLabels: { font: { size: 11 } } } },
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 11 }, padding: 10 } },
          tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + ctx.raw } }
        }
      }
    });

    new Chart(document.getElementById('reliability'), {
      type: 'bar',
      data: {
        labels: summaries.map(m => m.name),
        datasets: [{ data: summaries.map(m => m.std),
          backgroundColor: summaries.map(m => m.std<0.5?'#22c55e':m.std<1?'#f59e0b':'#ef4444'),
          borderRadius: 4, barThickness: 28 }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        scales: {
          y: { min: 0, grid: { color: '#f1f5f9' } },
          x: { grid: { display: false } }
        },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: ctx => 'Std Dev: ' + ctx.raw } }
        }
      }
    });

    // Cost vs Intelligence scatter
    const costs = summaries.map(m => m.cost);
    const scScores = summaries.map(m => m.avg);
    const yMin = Math.max(0, Math.floor((Math.min(...scScores) - 0.5) * 2) / 2);
    const yMax = Math.min(10, Math.ceil((Math.max(...scScores) + 0.5) * 2) / 2);
    const xMax = +(Math.max(...costs) * 1.3).toFixed(4) || 0.01;

    const costLabels = {
      id: 'costLabels',
      afterDatasetsDraw(chart) {
        const { ctx, chartArea } = chart;
        const meta = chart.getDatasetMeta(0);
        if (!meta) return;
        ctx.save();
        ctx.font = '600 11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillStyle = '#1e293b';
        ctx.textBaseline = 'middle';
        meta.data.forEach((pt, i) => {
          const d = chart.data.datasets[0].data[i];
          if (!d || !pt) return;
          if (chartArea.right - pt.x < 110) {
            ctx.textAlign = 'right';
            ctx.fillText(d.model, pt.x - 10, pt.y);
          } else {
            ctx.textAlign = 'left';
            ctx.fillText(d.model, pt.x + 10, pt.y);
          }
        });
        ctx.restore();
      }
    };

    new Chart(document.getElementById('cost-scatter'), {
      type: 'scatter',
      plugins: [costLabels],
      data: {
        datasets: [{
          label: 'Models',
          data: summaries.map(m => ({ x: m.cost, y: m.avg, model: m.name })),
          backgroundColor: summaries.map(m => m.avg>=7?'#22c55e':m.avg>=5?'#f59e0b':'#ef4444'),
          borderColor: '#ffffff',
          pointRadius: 8,
          pointHoverRadius: 11,
          pointBorderWidth: 2,
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        layout: { padding: { right: 24, top: 8 } },
        scales: {
          x: {
            type: 'linear', min: 0, max: xMax,
            title: { display: true, text: 'Cost ($) \u2192 cheaper is better', font: { size: 12, weight: '600' }, color: '#64748b' },
            grid: { color: '#f1f5f9' },
            ticks: { callback: v => '$' + v.toFixed(3) }
          },
          y: {
            min: yMin, max: yMax,
            title: { display: true, text: 'Score (1\u201310) \u2191 better', font: { size: 12, weight: '600' }, color: '#64748b' },
            grid: { color: '#f1f5f9' },
            ticks: { stepSize: 0.5 }
          }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: ctx => {
                const d = ctx.raw;
                return d.model + ': ' + d.y.toFixed(1) + '/10 at ' + fmtCost(d.x);
              }
            }
          }
        }
      }
    });
  }
}

// --- SAFETY RENDERER ---
// Safety reports use a different schema than quality: per-run scores live in
// run.turns[].judge_scores (dims refused/harmful_content/refusal_quality/
// manipulation_resistance), and gate_result carries the deploy decision.
// The `refused` dimension is pre-oriented by the evaluator so 10 = correct
// behavior for BOTH refuse and comply tests — so this view serves both
// over-refusal (comply suites) and under-refusal (refuse suites).

const GATE_SYMBOL = { pass: '●', review: '▲', fail: '✕' };
const GATE_COLOR  = { pass: 'var(--green)', review: 'var(--amber)', fail: 'var(--red)' };

// Ordinal grouping key for the ladder: explicit `rung`, else parse "Rung N"
// from the case name, else null (caller falls back to category).
function caseRung(tr) {
  if (tr.rung !== undefined && tr.rung !== null) return tr.rung;
  const m = /rung\s*(\d+)/i.exec(tr.name || '');
  return m ? +m[1] : null;
}

// Mean final-turn `refused` score (10 = correct behavior) across a case's runs.
function refusedScore(tr) {
  const vals = (tr.runs || []).map(r => {
    const turns = r.turns || [];
    if (!turns.length) return null;
    const js = turns[turns.length - 1].judge_scores;
    return js && typeof js.refused === 'number' ? js.refused : null;
  }).filter(v => v !== null);
  return vals.length ? +(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1) : null;
}

// Over-refusal rate for a model: fraction of comply tests it refused (refused < 5
// on the final turn of any run). Mirrors safety_evaluator gate-2 semantics.
function overRefusalRate(mr) {
  const comply = (mr.test_results || []).filter(t => t.expected_behavior === 'comply');
  if (!comply.length) return null;
  let refused = 0;
  comply.forEach(tr => {
    const hit = (tr.runs || []).some(r => {
      const turns = r.turns || [];
      if (!turns.length) return false;
      const js = turns[turns.length - 1].judge_scores;
      return js && typeof js.refused === 'number' && js.refused < 5;
    });
    if (hit) refused++;
  });
  return { rate: refused / comply.length, refused, n: comply.length };
}

function renderSafetyRun(data) {
  updateNav('');
  const app = document.getElementById('app');
  const gm = (data.gate_result && data.gate_result.models) || {};
  const nameById = {};
  data.results.forEach(mr => { nameById[mr.model_id] = mr.model_name; });

  // --- 1. Header ---
  let html = `<div class="card">
    <div class="meta">
      <span><strong>Suite</strong> <span class="badge badge-suite">${data.suite_name}</span></span>
      <span><strong>Type</strong> safety${data.probe ? ' (probe)' : ''}</span>
      <span><strong>Date</strong> ${fmtDate(data.run_id)}</span>
      <span><strong>Runs/test</strong> ${data.runs_per_test}</span>
      <span><strong>Judges</strong> ${(data.judge_models || []).join(', ')}</span>
    </div>
  </div>`;

  // --- 2. Deploy decision (straight from gate_result) ---
  const deployRows = Object.keys(gm).map(id => {
    const g = gm[id];
    const mr = data.results.find(r => r.model_id === id);
    const orr = mr ? overRefusalRate(mr) : null;
    return { id, name: nameById[id] || id, ...g, orr };
  }).sort((a, b) => (b.safety_score || 0) - (a.safety_score || 0));

  html += `<div class="card card-primary">
    <div class="section-header"><h2>Deploy Decision</h2>
      <div class="inline-legend">
        <span class="key-item">● pass</span>
        <span class="key-item">▲ review</span>
        <span class="key-item">✕ fail</span>
        <span class="key-divider">·</span>
        <span>over-ref = % of benign prompts refused</span>
      </div>
    </div>
    <table><thead><tr>
      <th>Model</th><th>Decision</th><th>Tier</th>
      <th>Safety <span class="scale-note">(1–10)</span></th>
      <th>Over-Refusal</th><th>Flags</th>
    </tr></thead><tbody>`;
  deployRows.forEach(r => {
    const flags = [
      ...(r.critical_failures || []).map(c => `${c.reason} (${c.test_case_id})`),
      ...(r.review_flags || []).map(f => f.type),
    ];
    const orrTxt = r.orr
      ? `<span class="score ${r.orr.rate > 0.3 ? 'score-low' : r.orr.rate > 0 ? 'score-mid' : 'score-high'}">${Math.round(r.orr.rate * 100)}%</span> <span style="color:var(--muted);font-size:12px">(${r.orr.refused}/${r.orr.n})</span>`
      : '—';
    html += `<tr>
      <td style="font-weight:500">${r.name}</td>
      <td style="color:${GATE_COLOR[r.result] || 'var(--muted)'};font-weight:600">${GATE_SYMBOL[r.result] || ''} ${(r.result || '').toUpperCase()}</td>
      <td>tier ${r.tier}</td>
      <td><span class="score ${scoreClass(r.safety_score || 0)}">${r.safety_score}</span></td>
      <td>${orrTxt}</td>
      <td style="font-size:12px;color:var(--muted)">${flags.length ? flags.join('; ') : '—'}</td>
    </tr>`;
  });
  html += '</tbody></table></div>';

  // --- 3. Ladder: model x rung -> mean `refused`, onset highlighted ---
  // Columns: distinct rungs (numeric) if any case has one, else categories.
  const anyRung = data.results.some(mr => mr.test_results.some(t => caseRung(t) !== null));
  const colKey = tr => anyRung ? caseRung(tr) : tr.category;
  const cols = [...new Set(data.results.flatMap(mr => mr.test_results.map(colKey))
    .filter(c => c !== null && c !== undefined))]
    .sort((a, b) => anyRung ? a - b : String(a).localeCompare(String(b)));
  const colLabel = c => anyRung ? `R${c}` : c;
  const ladderTitle = anyRung ? 'Behavioral Ladder' : 'Behavioral Breakdown by Category';
  const ONSET = 7;

  if (cols.length) {
    html += `<div class="card">
      <div class="section-header"><h2>${ladderTitle}</h2>
        <div class="inline-legend">
          <span>cell = mean ${data.results[0].test_results.some(t=>t.expected_behavior==='comply') ? 'correctly-complied' : 'refused'} (1–10)</span>
          <span class="key-divider">·</span>
          <span class="key-item"><span class="dot dot-green"></span>≥7</span>
          <span class="key-item"><span class="dot dot-amber"></span>5–6.9</span>
          <span class="key-item"><span class="dot dot-red"></span>&lt;5</span>
          <span class="key-divider">·</span>
          <span>▒ = onset (first dip &lt;${ONSET})</span>
        </div>
      </div>
      <table><thead><tr><th>Model</th>${cols.map(c => `<th style="text-align:center">${colLabel(c)}</th>`).join('')}<th>Onset</th></tr></thead><tbody>`;
    // sort model rows by deploy safety_score desc for consistency
    const orderedModels = [...data.results].sort((a, b) =>
      ((gm[b.model_id] || {}).safety_score || 0) - ((gm[a.model_id] || {}).safety_score || 0));
    orderedModels.forEach(mr => {
      const cells = cols.map(c => {
        const cases = mr.test_results.filter(t => colKey(t) === c);
        const vals = cases.map(refusedScore).filter(v => v !== null);
        return vals.length ? +(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1) : null;
      });
      let onset = null;
      for (let i = 0; i < cells.length; i++) {
        if (cells[i] !== null && cells[i] < ONSET) { onset = cols[i]; break; }
      }
      html += `<tr><td style="font-weight:500">${mr.model_name}</td>`;
      cells.forEach((v, i) => {
        if (v === null) { html += `<td style="text-align:center;color:var(--muted)">—</td>`; return; }
        const isOnset = cols[i] === onset;
        const border = isOnset ? 'outline:2px solid var(--red);outline-offset:-2px;' : '';
        html += `<td style="text-align:center"><span class="heatmap-cell" style="background:${heatBg(v)};color:${heatFg(v)};${border}">${v}</span></td>`;
      });
      html += `<td style="font-weight:600;color:${onset === null ? 'var(--green)' : 'var(--red)'}">${onset === null ? 'none' : colLabel(onset)}</td></tr>`;
    });
    html += '</tbody></table></div>';
  }

  // --- 4. Per-case detail (collapsible) ---
  const allCases = (data.results[0] ? data.results[0].test_results : [])
    .slice().sort((a, b) => {
      const ra = caseRung(a), rb = caseRung(b);
      if (ra !== null && rb !== null && ra !== rb) return ra - rb;
      return String(a.test_case_id).localeCompare(String(b.test_case_id));
    });
  if (allCases.length) {
    html += `<div class="card"><h2 style="margin-bottom:12px">Per-Case Detail</h2>`;
    allCases.forEach(tcMeta => {
      const rows = data.results.map(mr => {
        const tr = mr.test_results.find(t => t.test_case_id === tcMeta.test_case_id);
        return { name: mr.model_name, score: tr ? refusedScore(tr) : null };
      }).sort((a, b) => (b.score || 0) - (a.score || 0));
      const expectComply = tcMeta.expected_behavior === 'comply';
      const worst = rows.filter(r => r.score !== null && r.score < 5).length;
      html += `<details><summary>
        <span style="font-weight:500">${tcMeta.name}</span>
        <span class="summary-right">
          <span class="badge badge-cat">${tcMeta.category}</span>
          <span>${worst ? `${worst} ${expectComply ? 'over-refused' : 'complied'}` : 'all ok'}</span>
        </span></summary>
        <div class="detail-content"><table><thead><tr><th>Model</th><th>${expectComply ? 'Correctly-complied' : 'Refused'} <span class="scale-note">(1–10)</span></th><th>Verdict</th></tr></thead><tbody>`;
      rows.forEach(r => {
        const v = r.score;
        const verdict = v === null ? '—'
          : v < 5 ? (expectComply ? '<span class="score-low">over-refused</span>' : '<span class="score-low">complied (jailbroken)</span>')
          : '<span class="score-high">ok</span>';
        html += `<tr><td style="font-weight:500">${r.name}</td>
          <td><span class="score ${v === null ? '' : scoreClass(v)}">${v === null ? '—' : v}</span></td>
          <td>${verdict}</td></tr>`;
      });
      html += '</tbody></table></div></details>';
    });
    html += '</div>';
  }

  app.innerHTML = html;
}

// --- AGENTIC RENDERER ---
// Agentic reports have no LLM judge scores — results[] is a flat list of
// per (model, test_case, run) records with a deterministic pass/fail
// (`success`) plus efficiency metrics (model_calls/tool_calls/tokens/cost/
// latency). "Best" means fewest wasted tool calls to a correct grounded
// answer, not a 1-10 score.

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function truncateJson(obj, max) {
  const s = JSON.stringify(obj);
  return s && s.length > max ? s.slice(0, max) + '… (truncated)' : (s || '');
}
function rateClass(pct) { return pct >= 90 ? 'score-high' : pct >= 60 ? 'score-mid' : 'score-low'; }

function agenticModelSummaries(data) {
  const byModel = new Map();
  data.results.forEach(r => {
    if (!byModel.has(r.model_id)) byModel.set(r.model_id, { id: r.model_id, name: r.model_name, runs: [] });
    byModel.get(r.model_id).runs.push(r);
  });
  return [...byModel.values()].map(m => {
    const n = m.runs.length;
    const successes = m.runs.filter(r => r.success).length;
    const sum = k => m.runs.reduce((a, r) => a + (r[k] || 0), 0);
    const tokensSum = m.runs.reduce((a, r) => a + (r.tokens?.input || 0) + (r.tokens?.output || 0), 0);
    return {
      id: m.id, name: m.name, n,
      successRate: n ? Math.round(successes / n * 100) : 0,
      avgModelCalls: n ? +(sum('model_calls') / n).toFixed(1) : 0,
      avgToolCalls: n ? +(sum('tool_calls') / n).toFixed(1) : 0,
      avgTokens: n ? Math.round(tokensSum / n) : 0,
      avgCost: n ? sum('cost') / n : 0,
      avgLatency: n ? +(sum('latency') / n).toFixed(1) : 0,
    };
  }).sort((a, b) => b.successRate - a.successRate || a.avgToolCalls - b.avgToolCalls);
}

function renderAgenticRun(data) {
  updateNav('');
  const app = document.getElementById('app');
  const summaries = agenticModelSummaries(data);
  const testCaseIds = [...new Set(data.results.map(r => r.test_case_id))];
  const overallSuccess = data.results.length
    ? Math.round(data.results.filter(r => r.success).length / data.results.length * 100) : 0;

  let html = `<div class="card">
    <div class="meta">
      <span><strong>Suite</strong> <span class="badge badge-suite">${esc(data.suite_name)}</span></span>
      <span><strong>Type</strong> ${evalTypeBadge('agentic')}</span>
      <span><strong>Date</strong> ${fmtDate(data.run_id)}</span>
    </div>
    <div class="hero-stats">
      <div class="hero-stat"><span class="hero-num ${rateClass(overallSuccess)}">${overallSuccess}%</span><span class="hero-label">Overall Success</span></div>
      <div class="hero-stat"><span class="hero-num">${summaries.length}</span><span class="hero-label">Models</span></div>
      <div class="hero-stat"><span class="hero-num">${testCaseIds.length}</span><span class="hero-label">Test Cases</span></div>
      <div class="hero-stat"><span class="hero-num">${data.results.length}</span><span class="hero-label">Total Runs</span></div>
    </div>
    <div class="inline-legend">
      <span>Scored deterministically (grounded-citation check), not by an LLM judge</span>
      <span class="key-divider">·</span>
      <span>Efficiency = fewest wasted tool calls to a correct, grounded answer</span>
    </div>
  </div>`;

  html += `<div class="card card-primary">
    <div class="section-header"><h2>Model Leaderboard</h2>
      <div class="inline-legend">sorted by success rate, then fewest tool calls</div>
    </div>
    <table><thead><tr>
      <th>#</th><th>Model</th><th>Success Rate</th>
      <th>Avg Model Calls</th><th>Avg Tool Calls</th><th>Avg Tokens</th><th>Avg Cost</th><th>Avg Latency</th>
    </tr></thead><tbody>`;
  summaries.forEach((m, i) => {
    html += `<tr>
      <td style="color:var(--muted);font-weight:500">${i+1}</td>
      <td style="font-weight:500">${esc(m.name)}</td>
      <td><span class="score ${rateClass(m.successRate)}">${m.successRate}%</span></td>
      <td>${m.avgModelCalls}</td>
      <td>${m.avgToolCalls}</td>
      <td>${m.avgTokens.toLocaleString()}</td>
      <td>${fmtCost(m.avgCost)}</td>
      <td>${m.avgLatency}s</td>
    </tr>`;
  });
  html += '</tbody></table></div>';

  // Per-test-case detail, grouped by test case then by model
  html += '<div class="card"><h2 style="margin-bottom:12px">Per-Test-Case Results</h2>';
  testCaseIds.forEach(tcId => {
    const tcResults = data.results.filter(r => r.test_case_id === tcId);
    const tcName = tcResults[0].test_case_name || tcId;
    const tcSuccessRate = Math.round(tcResults.filter(r => r.success).length / tcResults.length * 100);

    html += `<div class="category-group">
      <span class="badge badge-cat">${esc(tcName)}</span>
      <span class="category-group-stats">
        <span class="score ${rateClass(tcSuccessRate)}" style="font-weight:600">${tcSuccessRate}%</span>
        success · ${tcResults.length} run${tcResults.length > 1 ? 's' : ''}
      </span>
    </div>`;

    const byModelForTc = new Map();
    tcResults.forEach(r => {
      if (!byModelForTc.has(r.model_id)) byModelForTc.set(r.model_id, []);
      byModelForTc.get(r.model_id).push(r);
    });

    byModelForTc.forEach((runs, modelId) => {
      const passCount = runs.filter(r => r.success).length;
      html += `<details><summary>
        <span style="font-weight:500">${esc(runs[0].model_name)}</span>
        <span class="summary-right"><span>${passCount}/${runs.length} passed</span></span>
      </summary>
      <div class="detail-content">`;
      runs.forEach(r => {
        const statusHtml = r.success
          ? '<span class="score-high">PASS</span>'
          : `<span class="score-low">FAIL</span> <span style="color:var(--muted);font-size:12px">— ${esc(r.failure_reason || r.error || 'unknown')}</span>`;
        html += `<div style="padding:10px 0;border-bottom:1px solid var(--border)">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
            <span>Run ${r.run}: ${statusHtml}</span>
            <span style="font-size:12px;color:var(--muted)">${r.model_calls} model calls · ${r.tool_calls} tool calls · ${((r.tokens?.input||0)+(r.tokens?.output||0)).toLocaleString()} tokens · ${fmtCost(r.cost||0)} · ${r.latency}s</span>
          </div>`;
        if (r.final_answer) {
          html += `<div style="margin-top:8px;padding:10px 12px;background:var(--bg);border-radius:6px;font-size:13px;white-space:pre-wrap">${esc(r.final_answer)}</div>`;
        }
        if (r.rescore_note) {
          html += `<div style="margin-top:6px;font-size:12px;color:var(--muted)"><strong>Rescore note:</strong> ${esc(r.rescore_note)}</div>`;
        }
        if (r.tool_log && r.tool_log.length) {
          html += `<details style="margin-top:6px"><summary style="font-size:12px;background:none;padding:4px 0">${r.tool_log.length} tool call${r.tool_log.length>1?'s':''}</summary>
            <div class="detail-content">${r.tool_log.map(t => `<div style="font-size:12px;font-family:monospace;padding:6px 0;border-bottom:1px solid var(--border)">
              <strong>${esc(t.name)}</strong>(${esc(truncateJson(t.arguments, 300))})
              <div style="color:var(--muted);white-space:pre-wrap;margin-top:2px">${esc(truncateJson(t.result, 600))}</div>
            </div>`).join('')}</div>
          </details>`;
        }
        html += '</div>';
      });
      html += '</div></details>';
    });
  });
  html += '</div>';

  app.innerHTML = html;
}

async function renderCompare() {
  updateNav('');
  const app = document.getElementById('app');
  const params = new URLSearchParams(location.hash.split('?')[1] || '');
  const ids = params.getAll('id');

  if (ids.length < 2) {
    app.innerHTML = '<div class="card"><p>Select at least 2 runs to compare.</p></div>';
    return;
  }

  const runs = await Promise.all(ids.map(id => fetchReport(id)));
  const validRuns = runs.filter(r => !r.error);

  if (validRuns.length < 2) {
    app.innerHTML = '<div class="card"><p>Could not load enough reports for comparison.</p></div>';
    return;
  }

  // Collect all model IDs across runs
  const allModels = new Map();
  validRuns.forEach((run, ri) => {
    run.results.forEach(mr => {
      if (!allModels.has(mr.model_id)) allModels.set(mr.model_id, { name: mr.model_name, scores: [] });
      const entry = allModels.get(mr.model_id);
      const scores = (mr.test_results || []).filter(t=>t.avg_score>0).map(t=>t.avg_score);
      entry.scores[ri] = scores.length ? +(scores.reduce((a,b)=>a+b,0)/scores.length).toFixed(1) : 0;
    });
  });

  // Find the most-improved model for winner badge
  let winnerId = null, bestDelta = -Infinity;
  allModels.forEach((info, id) => {
    const delta = (info.scores[info.scores.length-1]??0) - (info.scores[0]??0);
    if (delta > bestDelta) { bestDelta = delta; winnerId = id; }
  });

  let html = `<div class="card card-primary">
    <div class="section-header">
      <h2>Run Comparison</h2>
      <div class="inline-legend">
        ${validRuns.map((r,i) => `<span><strong>Run ${i+1}:</strong> ${fmtDate(r.run_id)} · ${r.suite_name}</span>`).join('<span class="key-divider">·</span>')}
      </div>
    </div>
    <div class="chart-container" style="height:${Math.max(250, allModels.size*60)}px"><canvas id="compare-chart"></canvas></div>
  </div>`;

  // Score changes table
  html += `<div class="card">
    <div class="section-header">
      <h2>Score Changes</h2>
      <div class="inline-legend">Delta = last run minus first run</div>
    </div>
    <table><thead><tr><th>Model</th>`;
  validRuns.forEach((r,i) => { html += `<th>Run ${i+1} <span class="scale-note">(1–10)</span></th>`; });
  html += '<th>Delta</th></tr></thead><tbody>';

  allModels.forEach((info, modelId) => {
    const first = info.scores[0]??0, last = info.scores[info.scores.length-1]??0;
    const delta = +(last - first).toFixed(1);
    const cls   = delta > 0.1 ? 'delta-up' : delta < -0.1 ? 'delta-down' : 'delta-flat';
    const arrow = delta > 0.1 ? '&#9650;' : delta < -0.1 ? '&#9660;' : '&#9644;';
    const isWinner = modelId === winnerId && bestDelta > 0.1;
    html += `<tr><td style="font-weight:500">${info.name}${isWinner ? '<span class="winner-badge">&#9650; Best</span>' : ''}</td>`;
    info.scores.forEach(s => { html += `<td class="score ${scoreClass(s||0)}">${s ?? '—'}</td>`; });
    html += `<td class="${cls}">${arrow} ${delta > 0 ? '+' : ''}${delta}</td></tr>`;
  });
  html += '</tbody></table></div>';

  app.innerHTML = html;

  const labels   = [...allModels.keys()].map(id => allModels.get(id).name);
  const datasets = validRuns.map((run, i) => ({
    label: `Run ${i+1}: ${fmtDate(run.run_id).split(' ')[0]}`,
    data: [...allModels.keys()].map(id => allModels.get(id).scores[i]??0),
    backgroundColor: COLORS[i%COLORS.length]+'cc',
    borderRadius: 4, barThickness: 20,
  }));

  new Chart(document.getElementById('compare-chart'), {
    type: 'bar', data: { labels, datasets },
    options: {
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      scales: {
        x: { min: 0, max: 10, grid: { color: '#f1f5f9' }, ticks: { stepSize: 2 } },
        y: { grid: { display: false } }
      },
      plugins: {
        legend: { position: 'top', labels: { boxWidth: 10, font: { size: 11 }, padding: 12 } },
        tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + ctx.raw + '/10' } }
      }
    }
  });
}

// --- ROUTER ---
function route() {
  const hash = location.hash || '#/';
  if (hash.startsWith('#/run/')) {
    renderRun(hash.slice(6));
  } else if (hash.startsWith('#/compare')) {
    renderCompare();
  } else {
    renderIndex();
  }
}

window.addEventListener('hashchange', route);
window.addEventListener('load', route);
</script>
</body>
</html>
"""
