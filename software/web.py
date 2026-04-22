import streamlit as st
import requests

st.set_page_config(page_title="Motor Diagnostic UI", layout="wide")
st.title("⚙️ B2B Motor Diagnostic Dashboard")

API_URL = "http://127.0.0.1:8000"

MAX_POINTS = 100  # scrolling window size (like Task Manager)

col1, col2, col3 = st.columns(3)

# ==========================================
# ACTION 1: CALIBRATE (1000 Readings)
# Deletes ALL previous data, then reads fresh
# ==========================================
with col1:
    st.subheader("Step 1: Calibration")
    if st.button("▶ Action 1: Read 1000 Values"):

        with st.spinner("🗑️ Clearing old data & recording 1000 fresh readings (~20 sec)..."):
            try:
                res = requests.post(f"{API_URL}/api/action1_calibrate", timeout=60)
                if res.status_code == 200:
                    st.success("✅ Calibration Complete! 1000 new readings saved.")
                else:
                    st.error(f"Backend error: {res.status_code}")
            except requests.exceptions.ConnectionError:
                st.error("❌ Backend not running! Start `uvicorn main:app` first.")

# ==========================================
# ACTION 3: VIEW DISTRIBUTION
# ==========================================
with col3:
    st.subheader("Step 2: Distribution")
    if st.button("▶ Action 3: Show Distribution"):
        try:
            res = requests.get(f"{API_URL}/api/action3_distribution", timeout=10)
            if res.status_code == 200:
                st.image(res.content, caption="Vibration Magnitude Distribution √(x² + y² + z²)")
            else:
                st.error(f"Backend error: {res.status_code}")
        except requests.exceptions.ConnectionError:
            st.error("❌ Backend not running!")

st.divider()


# ==========================================
# LIVE CHART — Pure JS, polls API directly from browser
# Plotly.react() updates chart in-place = zero flicker
# ==========================================
import streamlit.components.v1 as components

LIVE_CHART_HTML = f"""
<!DOCTYPE html>
<html>
<head>
<script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: transparent; font-family: 'Segoe UI', sans-serif; }}
  #chart {{ width: 100%; height: 420px; }}
  #status {{ color: #a0a0a0; font-size: 13px; padding: 8px 12px; }}
  #controls {{ display: flex; gap: 12px; margin-bottom: 8px; }}
  #controls button {{
    padding: 8px 24px; border: none; border-radius: 6px; cursor: pointer;
    font-size: 14px; font-weight: 600; transition: all 0.2s;
  }}
  #btnStart {{
    background: linear-gradient(135deg, #00c853, #00e676); color: #fff;
  }}
  #btnStart:hover {{ transform: scale(1.04); box-shadow: 0 4px 16px rgba(0,200,80,0.3); }}
  #btnStop {{
    background: linear-gradient(135deg, #ff1744, #ff5252); color: #fff;
  }}
  #btnStop:hover {{ transform: scale(1.04); box-shadow: 0 4px 16px rgba(255,50,50,0.3); }}
  #btnStart:disabled, #btnStop:disabled {{
    opacity: 0.4; cursor: not-allowed; transform: none; box-shadow: none;
  }}
</style>
</head>
<body>

<div id="controls">
  <button id="btnStart" onclick="startStream()">▶ Start Live Stream</button>
  <button id="btnStop" onclick="stopStream()" disabled>⏹ Stop Live Stream</button>
</div>
<div id="chart"></div>
<div id="status">⏸ Click "Start Live Stream" to begin.</div>

<script>
const API = "{API_URL}";
const MAX = {MAX_POINTS};
let dataX = [], dataY = [], dataZ = [];
let avgX = 0, avgY = 0, avgZ = 0;
let timer = null;
let chartReady = false;

// ── Initialize empty chart ──
const layout = {{
  title: {{ text: 'Live Vibration — X · Y · Z  (Scroll to Zoom)', font: {{ color: '#fff', size: 16 }} }},
  paper_bgcolor: '#1a1a2e',
  plot_bgcolor: '#16213e',
  font: {{ color: '#a0a0a0' }},
  height: 420,
  margin: {{ l: 50, r: 30, t: 60, b: 50 }},
  legend: {{
    orientation: 'h', yanchor: 'bottom', y: 1.02, xanchor: 'center', x: 0.5,
    font: {{ color: '#fff', size: 13 }}, bgcolor: 'rgba(0,0,0,0.3)'
  }},
  xaxis: {{
    title: 'Reading #', showgrid: true, gridcolor: '#2a2a4a', gridwidth: 1,
    range: [0, MAX],
    rangeslider: {{ visible: true, bgcolor: '#0f0f23', thickness: 0.08 }}
  }},
  yaxis: {{
    title: 'Sensor Value', showgrid: true, gridcolor: '#2a2a4a', gridwidth: 1
  }},
  dragmode: 'zoom',
  shapes: [],
  annotations: []
}};

const traces = [
  {{ y: [], mode: 'lines', name: 'X-Axis', line: {{ color: 'rgba(255,60,60,1)', width: 2 }},
     fill: 'tozeroy', fillcolor: 'rgba(255,60,60,0.08)' }},
  {{ y: [], mode: 'lines', name: 'Y-Axis', line: {{ color: 'rgba(60,255,60,1)', width: 2 }},
     fill: 'tozeroy', fillcolor: 'rgba(60,255,60,0.08)' }},
  {{ y: [], mode: 'lines', name: 'Z-Axis', line: {{ color: 'rgba(60,120,255,1)', width: 2 }},
     fill: 'tozeroy', fillcolor: 'rgba(60,120,255,0.08)' }}
];

const config = {{ scrollZoom: true, displayModeBar: true, responsive: true }};

Plotly.newPlot('chart', traces, layout, config).then(() => {{ chartReady = true; }});

// ── Smooth update function ──
async function fetchAndUpdate() {{
  try {{
    const res = await fetch(API + '/api/action2_live');
    const data = await res.json();

    const live = data.live;
    const avg = data.averages;
    avgX = avg.avg_x; avgY = avg.avg_y; avgZ = avg.avg_z;

    dataX.push(live.x); dataY.push(live.y); dataZ.push(live.z);
    if (dataX.length > MAX) {{ dataX.shift(); dataY.shift(); dataZ.shift(); }}

    // Build avg lines as shapes + annotations
    const shapes = [];
    const annotations = [];
    const avgLines = [
      {{ val: avgX, color: 'rgba(255,60,60,0.6)', label: 'Avg X', fontColor: 'rgba(255,60,60,1)', pos: 'left' }},
      {{ val: avgY, color: 'rgba(60,255,60,0.6)', label: 'Avg Y', fontColor: 'rgba(60,255,60,1)', pos: 'right' }},
      {{ val: avgZ, color: 'rgba(60,120,255,0.6)', label: 'Avg Z', fontColor: 'rgba(60,120,255,1)', pos: 'center' }}
    ];
    avgLines.forEach(a => {{
      if (a.val !== 0) {{
        shapes.push({{
          type: 'line', x0: 0, x1: 1, xref: 'paper', y0: a.val, y1: a.val,
          line: {{ color: a.color, width: 1.5, dash: 'dash' }}
        }});
        annotations.push({{
          x: a.pos === 'left' ? 0.02 : a.pos === 'right' ? 0.98 : 0.5,
          xref: 'paper', xanchor: a.pos === 'right' ? 'end' : 'start',
          y: a.val, yanchor: 'bottom',
          text: a.label + ': ' + a.val.toFixed(2),
          showarrow: false, font: {{ color: a.fontColor, size: 11 }}
        }});
      }}
    }});

    // Plotly.react = in-place update, NO DOM replacement
    Plotly.react('chart', [
      {{ ...traces[0], y: [...dataX] }},
      {{ ...traces[1], y: [...dataY] }},
      {{ ...traces[2], y: [...dataZ] }}
    ], {{ ...layout, shapes, annotations }}, config);

    document.getElementById('status').innerHTML =
      '📡 Live — X: ' + live.x.toFixed(2) + '  |  Y: ' + live.y.toFixed(2) +
      '  |  Z: ' + live.z.toFixed(2) +
      '  (Avg X: ' + avgX.toFixed(2) + ', Y: ' + avgY.toFixed(2) + ', Z: ' + avgZ.toFixed(2) + ')';

  }} catch(e) {{
    document.getElementById('status').innerHTML = '❌ Backend not running! Start uvicorn main:app first.';
    stopStream();
  }}
}}

function startStream() {{
  if (timer) return;
  dataX = []; dataY = []; dataZ = [];
  document.getElementById('btnStart').disabled = true;
  document.getElementById('btnStop').disabled = false;
  document.getElementById('status').innerHTML = '📡 Connecting...';
  fetchAndUpdate();
  timer = setInterval(fetchAndUpdate, 1000);
}}

function stopStream() {{
  if (timer) {{ clearInterval(timer); timer = null; }}
  document.getElementById('btnStart').disabled = false;
  document.getElementById('btnStop').disabled = true;
  document.getElementById('status').innerHTML = '⏸ Live stream stopped. Click "Start Live Stream" to begin.';
}}
</script>
</body>
</html>
"""

components.html(LIVE_CHART_HTML, height=540, scrolling=False)

st.divider()

# ==========================================
# SECTION 4: LIVE ANOMALY DETECTION (Z-Score)
# ==========================================
st.subheader("Step 4: Live Anomaly Detection (Z-Score)")

ANOMALY_HTML = f"""
<!DOCTYPE html>
<html>
<head>
<script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: transparent; font-family: 'Inter', 'Segoe UI', sans-serif; }}

  .anomaly-container {{ padding: 8px 0; }}

  /* Overall status banner */
  .overall-banner {{
    text-align: center; padding: 18px 30px; border-radius: 14px;
    margin-bottom: 16px; transition: all 0.5s ease;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  }}
  .overall-banner.normal {{
    background: linear-gradient(135deg, #0d3320, #155d3e);
    border: 2px solid #00e676;
  }}
  .overall-banner.anomaly {{
    background: linear-gradient(135deg, #3d0a0a, #6b1515);
    border: 2px solid #ff1744;
    animation: pulse-red 1.5s ease-in-out infinite;
  }}
  @keyframes pulse-red {{
    0%, 100% {{ box-shadow: 0 8px 32px rgba(255,23,68,0.3); }}
    50% {{ box-shadow: 0 8px 48px rgba(255,23,68,0.6); }}
  }}
  .overall-icon {{ font-size: 36px; margin-bottom: 4px; }}
  .overall-text {{ font-size: 20px; font-weight: 900; letter-spacing: 1px; }}
  .overall-sub {{ font-size: 12px; color: #a0a0a0; margin-top: 4px; }}

  /* Z-score chart */
  #zscoreChart {{ width: 100%; height: 340px; margin-bottom: 16px; }}

  /* Axis cards row */
  .axis-row {{ display: flex; gap: 14px; }}
  .axis-card {{
    flex: 1; border-radius: 12px; padding: 16px 18px;
    transition: all 0.4s ease; position: relative; overflow: hidden;
    box-shadow: 0 4px 20px rgba(0,0,0,0.25);
  }}
  .axis-card.normal {{
    background: linear-gradient(145deg, #1a2e1a, #1e3a20);
    border: 1.5px solid rgba(0,230,118,0.3);
  }}
  .axis-card.anomaly {{
    background: linear-gradient(145deg, #2e1a1a, #3a1e1e);
    border: 1.5px solid rgba(255,23,68,0.5);
    animation: card-glow 2s ease-in-out infinite;
  }}
  @keyframes card-glow {{
    0%, 100% {{ border-color: rgba(255,23,68,0.4); }}
    50% {{ border-color: rgba(255,23,68,0.9); }}
  }}

  .axis-label {{ font-size: 12px; color: #888; font-weight: 600; text-transform: uppercase; letter-spacing: 2px; }}
  .axis-zscore {{ font-size: 26px; font-weight: 900; margin: 4px 0; }}
  .axis-zscore.normal {{ color: #00e676; }}
  .axis-zscore.anomaly {{ color: #ff1744; }}

  .axis-detail {{ font-size: 11px; color: #999; line-height: 1.8; }}
  .axis-detail span {{ color: #ccc; font-weight: 600; }}

  .z-score-bar {{
    height: 6px; border-radius: 3px; background: #2a2a4a;
    margin-top: 8px; overflow: hidden; position: relative;
  }}
  .z-score-fill {{
    height: 100%; border-radius: 3px; transition: width 0.4s ease, background 0.4s ease;
  }}
  .z-score-fill.normal {{ background: linear-gradient(90deg, #00c853, #00e676); }}
  .z-score-fill.anomaly {{ background: linear-gradient(90deg, #ff1744, #ff5252); }}

  .badge {{
    display: inline-block; padding: 3px 10px; border-radius: 20px;
    font-size: 11px; font-weight: 700; margin-top: 6px; letter-spacing: 0.5px;
  }}
  .badge.normal {{ background: rgba(0,230,118,0.15); color: #00e676; }}
  .badge.anomaly {{ background: rgba(255,23,68,0.15); color: #ff1744; }}

  .waiting {{ text-align: center; color: #666; padding: 40px; font-size: 15px; }}

  /* Start/Stop controls */
  .controls {{ display: flex; gap: 12px; margin-bottom: 14px; }}
  .controls button {{
    padding: 8px 24px; border: none; border-radius: 6px; cursor: pointer;
    font-size: 14px; font-weight: 600; transition: all 0.2s;
  }}
  .btn-start {{ background: linear-gradient(135deg, #00c853, #00e676); color: #fff; }}
  .btn-start:hover {{ transform: scale(1.04); box-shadow: 0 4px 16px rgba(0,200,80,0.3); }}
  .btn-stop {{ background: linear-gradient(135deg, #ff1744, #ff5252); color: #fff; }}
  .btn-stop:hover {{ transform: scale(1.04); box-shadow: 0 4px 16px rgba(255,50,50,0.3); }}
  .btn-start:disabled, .btn-stop:disabled {{ opacity: 0.4; cursor: not-allowed; transform: none; box-shadow: none; }}

  /* Formula box */
  .formula-box {{
    background: #0f0f23; border: 1px solid #2a2a4a; border-radius: 10px;
    padding: 12px 18px; margin-bottom: 14px;
    font-size: 13px; color: #b0b0b0; display: flex; align-items: center; gap: 14px;
  }}
  .formula-box .formula {{
    color: #e0e0e0; font-family: 'Courier New', monospace; font-size: 14px; font-weight: 700;
  }}
  .formula-box .sep {{ color: #444; }}
</style>
</head>
<body>

<div class="anomaly-container">
  <div class="controls">
    <button class="btn-start" id="aStart" onclick="startAnomaly()">▶ Start Anomaly Monitor</button>
    <button class="btn-stop" id="aStop" onclick="stopAnomaly()" disabled>⏹ Stop</button>
  </div>

  <div class="formula-box">
    <span class="formula">Z = (|x| − μ) / σ</span>
    <span class="sep">|</span>
    <span>Threshold: <b style="color:#ff9800">±3σ</b></span>
    <span class="sep">|</span>
    <span>|Z| &gt; 3 → <b style="color:#ff1744">Anomaly</b></span>
  </div>

  <div id="anomalyContent">
    <div class="waiting">⏸ Click "Start Anomaly Monitor" to begin real-time Z-Score detection.</div>
  </div>
</div>

<script>
const API_A = "{API_URL}";
let anomalyTimer = null;
let chartInitialized = false;

// ── Initialize Z-Score chart ──
const zLayout = {{
  title: {{ text: 'Live Z-Score — X · Y · Z  (Anomaly if |Z| > 3)', font: {{ color: '#fff', size: 14 }} }},
  paper_bgcolor: '#1a1a2e',
  plot_bgcolor: '#16213e',
  font: {{ color: '#a0a0a0' }},
  height: 340,
  margin: {{ l: 50, r: 30, t: 50, b: 40 }},
  legend: {{
    orientation: 'h', yanchor: 'bottom', y: 1.02, xanchor: 'center', x: 0.5,
    font: {{ color: '#fff', size: 12 }}, bgcolor: 'rgba(0,0,0,0.3)'
  }},
  xaxis: {{
    title: 'Reading #', showgrid: true, gridcolor: '#2a2a4a', gridwidth: 1
  }},
  yaxis: {{
    title: 'Z-Score', showgrid: true, gridcolor: '#2a2a4a', gridwidth: 1,
    zeroline: true, zerolinecolor: '#444', zerolinewidth: 1
  }},
  shapes: [
    // +3 threshold line
    {{ type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 3, y1: 3,
       line: {{ color: 'rgba(255,152,0,0.7)', width: 2, dash: 'dash' }} }},
    // -3 threshold line
    {{ type: 'line', x0: 0, x1: 1, xref: 'paper', y0: -3, y1: -3,
       line: {{ color: 'rgba(255,152,0,0.7)', width: 2, dash: 'dash' }} }},
    // 0 baseline
    {{ type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 0, y1: 0,
       line: {{ color: 'rgba(255,255,255,0.15)', width: 1 }} }}
  ],
  annotations: [
    {{ x: 1, xref: 'paper', xanchor: 'right', y: 3.2, yanchor: 'bottom',
       text: '+3σ Threshold', showarrow: false, font: {{ color: '#ff9800', size: 11 }} }},
    {{ x: 1, xref: 'paper', xanchor: 'right', y: -3.2, yanchor: 'top',
       text: '−3σ Threshold', showarrow: false, font: {{ color: '#ff9800', size: 11 }} }}
  ]
}};

const zTraces = [
  {{ x: [], y: [], mode: 'lines+markers', name: 'X Z-Score',
     line: {{ color: 'rgba(255,60,60,1)', width: 2 }},
     marker: {{ size: 4, color: 'rgba(255,60,60,0.8)' }} }},
  {{ x: [], y: [], mode: 'lines+markers', name: 'Y Z-Score',
     line: {{ color: 'rgba(60,255,60,1)', width: 2 }},
     marker: {{ size: 4, color: 'rgba(60,255,60,0.8)' }} }},
  {{ x: [], y: [], mode: 'lines+markers', name: 'Z Z-Score',
     line: {{ color: 'rgba(60,120,255,1)', width: 2 }},
     marker: {{ size: 4, color: 'rgba(60,120,255,0.8)' }} }}
];

const zConfig = {{ scrollZoom: true, displayModeBar: true, responsive: true }};


function buildCard(axis, d) {{
  const cls = d.is_anomaly ? 'anomaly' : 'normal';
  const statusText = d.is_anomaly ? '⚠ ANOMALY' : '✓ NORMAL';
  // Clamp z-score bar to 0-100% (where 3σ = 50%, 6σ = 100%)
  const barPct = Math.min(Math.abs(d.z_score) / 6 * 100, 100);

  const ub = d.upper_bound !== undefined ? d.upper_bound.toFixed(4) : '—';
  const lb = d.lower_bound !== undefined ? d.lower_bound.toFixed(4) : '—';

  return `
    <div class="axis-card ${{cls}}">
      <div class="axis-label">${{axis.toUpperCase()}}-Axis</div>
      <div class="axis-zscore ${{cls}}">Z = ${{d.z_score.toFixed(3)}}</div>
      <div class="axis-detail">
        Live: <span>${{d.value.toFixed(4)}}</span><br>
        μ: <span>${{d.mean.toFixed(4)}}</span> &nbsp;|&nbsp; σ: <span>${{d.std.toFixed(4)}}</span><br>
        Range: <span>${{lb}}</span> — <span>${{ub}}</span>
      </div>
      <div class="z-score-bar">
        <div class="z-score-fill ${{cls}}" style="width: ${{barPct}}%"></div>
      </div>
      <div class="badge ${{cls}}">${{statusText}}</div>
    </div>
  `;
}}

async function fetchAnomaly() {{
  try {{
    const res = await fetch(API_A + '/api/action4_anomaly');
    const data = await res.json();

    if (data.error) {{
      document.getElementById('anomalyContent').innerHTML =
        '<div class="waiting">⚠️ ' + data.error + '</div>';
      return;
    }}

    const axes = data.axes;
    const overall = data.overall_anomaly;
    const history = data.history || [];

    // ── Update Z-Score chart ──
    if (!chartInitialized) {{
      // Create the chart div if it doesn't exist
      let chartDiv = document.getElementById('zscoreChart');
      if (!chartDiv) {{
        chartDiv = document.createElement('div');
        chartDiv.id = 'zscoreChart';
        const content = document.getElementById('anomalyContent');
        content.parentNode.insertBefore(chartDiv, content);
      }}
      Plotly.newPlot('zscoreChart', zTraces, zLayout, zConfig);
      chartInitialized = true;
    }}

    // Extract history arrays
    const ticks = history.map(h => h.tick);
    const zx = history.map(h => h.x);
    const zy = history.map(h => h.y);
    const zz = history.map(h => h.z);

    // Find anomaly points for scatter markers
    const anomalyTicks = [], anomalyZ = [];
    history.forEach(h => {{
      if (h.anomaly) {{
        // Plot the max |z| for that tick as a marker
        const maxZ = [h.x, h.y, h.z].reduce((a, b) => Math.abs(a) > Math.abs(b) ? a : b, 0);
        anomalyTicks.push(h.tick);
        anomalyZ.push(maxZ);
      }}
    }});

    Plotly.react('zscoreChart', [
      {{ ...zTraces[0], x: ticks, y: zx }},
      {{ ...zTraces[1], x: ticks, y: zy }},
      {{ ...zTraces[2], x: ticks, y: zz }},
      // Anomaly markers overlay
      {{ x: anomalyTicks, y: anomalyZ, mode: 'markers', name: '🚨 Anomaly',
         marker: {{ size: 12, color: 'rgba(255,23,68,0.9)', symbol: 'x', line: {{ width: 2, color: '#fff' }} }},
         showlegend: anomalyTicks.length > 0 }}
    ], zLayout, zConfig);

    // ── Build status banner + cards ──
    const cls = overall ? 'anomaly' : 'normal';
    const icon = overall ? '🚨' : '✅';
    const text = overall ? 'ANOMALY DETECTED' : 'ALL NORMAL';
    const sub = overall
      ? 'One or more axes exceeded ±3σ threshold — investigate immediately!'
      : 'All axes within normal operating range (±3σ)';

    let html = `
      <div class="overall-banner ${{cls}}">
        <div class="overall-icon">${{icon}}</div>
        <div class="overall-text" style="color: ${{overall ? '#ff1744' : '#00e676'}}">${{text}}</div>
        <div class="overall-sub">${{sub}}</div>
      </div>
      <div class="axis-row">
    `;

    for (const axis of ['x', 'y', 'z']) {{
      html += buildCard(axis, axes[axis]);
    }}
    html += '</div>';

    document.getElementById('anomalyContent').innerHTML = html;

  }} catch(e) {{
    document.getElementById('anomalyContent').innerHTML =
      '<div class="waiting">❌ Backend not running!</div>';
    stopAnomaly();
  }}
}}

function startAnomaly() {{
  if (anomalyTimer) return;
  chartInitialized = false;
  document.getElementById('aStart').disabled = true;
  document.getElementById('aStop').disabled = false;
  document.getElementById('anomalyContent').innerHTML =
    '<div class="waiting">📡 Connecting to anomaly detector...</div>';
  fetchAnomaly();
  anomalyTimer = setInterval(fetchAnomaly, 1000);
}}

function stopAnomaly() {{
  if (anomalyTimer) {{ clearInterval(anomalyTimer); anomalyTimer = null; }}
  document.getElementById('aStart').disabled = false;
  document.getElementById('aStop').disabled = true;
}}
</script>
</body>
</html>
"""

components.html(ANOMALY_HTML, height=880, scrolling=False)