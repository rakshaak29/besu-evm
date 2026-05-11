// ── State ────────────────────────────────────────────────────────
let indexData = null;
let trendsData = null;
let charts = {
  overview: null,
  trend: null,
  sparklines: {}
};

const COLORS = {
  accent: '#4c6fff',
  green: '#1f9d61',
  red: '#d6455d',
  yellow: '#b48118',
  purple: '#7a63d5',
  cyan: '#299ab8',
  orange: '#d9772f',
  muted: '#637392',
  border: '#d8e1f0'
};

const CAT_COLORS = {
  arithmetic: COLORS.accent,
  bitwise: COLORS.purple,
  stack: COLORS.green,
  memory: COLORS.cyan,
  crypto: COLORS.orange,
  calls: COLORS.yellow,
  other: COLORS.muted
};

// ── Init ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  setupTabs();
  
  try {
    const [idxRes, trnRes] = await Promise.all([
      fetch('data/index.json'),
      fetch('data/trends.json')
    ]);
    
    indexData = await idxRes.json();
    trendsData = await trnRes.json();
    
    renderHero();
    renderOverview();
    renderBenchmarksTab();
    renderTrendsTab();
    renderRunsTab();
    
  } catch (err) {
    console.error('Failed to load dashboard data:', err);
    document.getElementById('footer-updated').textContent = 'Error loading data';
  }
});

// ── Tabs ─────────────────────────────────────────────────────────
function setupTabs() {
  document.querySelectorAll('.nav-link[data-tab]').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      
      // Update nav
      document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
      e.target.classList.add('active');
      
      // Update sections
      const targetId = e.target.getAttribute('data-tab');
      document.querySelectorAll('.tab-section').forEach(s => s.classList.add('hidden'));
      document.getElementById(`tab-${targetId}`).classList.remove('hidden');
      
      // Handle resizing if a chart is in the tab
      if (targetId === 'overview' && charts.overview) charts.overview.resize();
      if (targetId === 'trends' && charts.trend) charts.trend.resize();
      
      // Update URL hash without jumping
      history.replaceState(null, null, `#${targetId}`);
    });
  });
  
  // Initial tab from hash
  const hash = window.location.hash.replace('#', '');
  if (hash) {
    const link = document.querySelector(`.nav-link[data-tab="${hash}"]`);
    if (link) link.click();
  }
}

// ── Rendering: Hero ──────────────────────────────────────────────
function renderHero() {
  document.getElementById('val-runs').textContent = indexData.total_runs;
  document.getElementById('val-benchmarks').textContent = indexData.total_benchmarks;
  
  if (indexData.runs && indexData.runs.length > 0) {
    const latestRun = indexData.runs[0];
    document.getElementById('val-latest-ref').innerHTML = `
      ${latestRun.besu_ref} <span style="font-size:0.6em;color:var(--text-muted)">(${latestRun.besu_sha.substring(0,7)})</span>
    `;
  }
  
  const rc = indexData.regressions.length;
  const elReg = document.getElementById('val-regressions');
  elReg.textContent = rc;
  if (rc > 0) {
    document.getElementById('stat-regressions').classList.add('has-regressions');
  }
  
  const d = new Date(indexData.generated_at);
  document.getElementById('footer-updated').textContent = d.toLocaleString();
}

// ── Rendering: Overview ──────────────────────────────────────────
function renderOverview() {
  // Regressions
  if (indexData.regressions && indexData.regressions.length > 0) {
    const wrap = document.getElementById('regression-alerts');
    wrap.classList.remove('hidden');
    let html = `<h3>⚠️ Action Required: ${indexData.regressions.length} Performance Regression(s) Detected</h3><ul>`;
    indexData.regressions.forEach(r => {
      html += `<li><strong>${r.name}</strong> dropped by <span style="font-family:var(--mono);font-weight:bold">${r.pct_change.toFixed(1)}%</span> (from ${r.prev_score.toFixed(1)} to ${r.curr_score.toFixed(1)} ${r.unit}) in ref <code>${r.curr_ref}</code>.</li>`;
    });
    html += `</ul>`;
    wrap.innerHTML = html;
  }
  
  // Category cards
  const cats = {};
  indexData.latest.forEach(b => {
    if (!cats[b.category]) cats[b.category] = { count: 0, best: null };
    cats[b.category].count++;
    if (!cats[b.category].best || b.score > cats[b.category].best.score) {
      cats[b.category].best = b;
    }
  });
  
  const grid = document.getElementById('category-grid');
  let catHtml = '';
  Object.keys(cats).sort().forEach(c => {
    const d = cats[c];
    catHtml += `
      <div class="cat-card cat-${c}" onclick="document.querySelector('.nav-link[data-tab=\\'benchmarks\\']').click(); setTimeout(()=>filterCategory('${c}'),10)">
        <div class="cat-name">${c}</div>
        <div class="cat-count">${d.count} benchmarks</div>
        <div class="cat-best">Top: ${d.best.name} (${d.best.score.toFixed(0)} ${d.best.score_unit})</div>
      </div>
    `;
  });
  grid.innerHTML = catHtml;
  
  // Overview Chart (Top 10 by score)
  const sorted = [...indexData.latest].sort((a,b) => b.score - a.score).slice(0, 15);
  const ctx = document.getElementById('overviewChart').getContext('2d');
  
  Chart.defaults.color = COLORS.muted;
  Chart.defaults.font.family = "'Inter', sans-serif";
  
  charts.overview = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sorted.map(b => b.name),
      datasets: [{
        label: 'Score (MGps)',
        data: sorted.map(b => b.score),
        backgroundColor: sorted.map(b => CAT_COLORS[b.category] || COLORS.muted),
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        y: {
          beginAtZero: true,
          grid: { color: COLORS.border }
        },
        x: {
          grid: { display: false },
          ticks: { maxRotation: 45, minRotation: 45 }
        }
      }
    }
  });
}

// ── Rendering: Benchmarks Tab ────────────────────────────────────
let currentFilter = 'all';

function filterCategory(cat) {
  currentFilter = cat;
  document.querySelectorAll('.filter-chips .chip').forEach(c => {
    if (c.dataset.cat === cat) c.classList.add('active');
    else c.classList.remove('active');
  });
  renderBenchTable();
}

function renderBenchmarksTab() {
  // Setup filters
  const cats = new Set(indexData.latest.map(b => b.category));
  let chips = `<button class="chip active" data-cat="all" onclick="filterCategory('all')">All</button>`;
  Array.from(cats).sort().forEach(c => {
    chips += `<button class="chip" data-cat="${c}" onclick="filterCategory('${c}')">${c}</button>`;
  });
  document.getElementById('category-filters').innerHTML = chips;
  
  // Setup search & sort
  document.getElementById('bench-search').addEventListener('input', renderBenchTable);
  document.getElementById('bench-sort').addEventListener('change', renderBenchTable);
  
  renderBenchTable();
}

function renderBenchTable() {
  const query = document.getElementById('bench-search').value.toLowerCase();
  const sort = document.getElementById('bench-sort').value;
  
  let list = indexData.latest.filter(b => {
    if (currentFilter !== 'all' && b.category !== currentFilter) return false;
    if (query && !b.name.toLowerCase().includes(query)) return false;
    return true;
  });
  
  list.sort((a,b) => {
    if (sort === 'score-desc') return b.score - a.score;
    if (sort === 'score-asc') return a.score - b.score;
    if (sort === 'name-asc') return a.name.localeCompare(b.name);
    if (sort === 'name-desc') return b.name.localeCompare(a.name);
    if (sort === 'category') return a.category.localeCompare(b.category) || (b.score - a.score);
    return 0;
  });
  
  const tbody = document.getElementById('bench-tbody');
  let html = '';
  
  list.forEach(b => {
    const tr = trendsData[b.name];
    let pct = 0;
    if (tr && tr.length >= 2) {
      const prev = tr[tr.length-2].score;
      const curr = tr[tr.length-1].score;
      if (prev > 0) pct = ((curr - prev) / prev) * 100;
    }
    
    let pctCls = 'change-neutral';
    let pctTxt = '—';
    if (Math.abs(pct) > 1.0) {
      pctTxt = (pct > 0 ? '+' : '') + pct.toFixed(1) + '%';
      pctCls = pct > 0 ? 'change-pos' : 'change-neg';
    }
    
    html += `
      <tr>
        <td>
          <a href="#" class="bench-name" onclick="openTrend('${b.name}'); return false;">${b.name}</a>
        </td>
        <td><span class="bench-cat">${b.category}</span></td>
        <td class="bench-score">${b.score.toFixed(1)}</td>
        <td class="bench-unit">${b.score_unit}</td>
        <td class="${pctCls}">${pctTxt}</td>
        <td>
          <div class="sparkline" style="width:100px; height:24px;">
            <canvas id="spark-${b.name}"></canvas>
          </div>
        </td>
      </tr>
    `;
  });
  
  tbody.innerHTML = html;
  
  // Render sparklines
  list.forEach(b => {
    const tr = trendsData[b.name];
    if (!tr || tr.length < 2) return;
    
    const ctx = document.getElementById(`spark-${b.name}`);
    if (!ctx) return;
    
    const color = CAT_COLORS[b.category] || COLORS.accent;
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: tr.map(t => t.timestamp),
        datasets: [{
          data: tr.map(t => t.score),
          borderColor: color,
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: { x: { display: false }, y: { display: false } },
        animation: false
      }
    });
  });
}

// ── Rendering: Trends Tab ────────────────────────────────────────
function renderTrendsTab() {
  const sel = document.getElementById('trend-select');
  const catSel = document.getElementById('trend-category');
  
  // Populate categories
  const cats = new Set(indexData.latest.map(b => b.category));
  Array.from(cats).sort().forEach(c => {
    const opt = document.createElement('option');
    opt.value = c; opt.textContent = c.charAt(0).toUpperCase() + c.slice(1);
    catSel.appendChild(opt);
  });
  
  catSel.addEventListener('change', () => populateTrendSelect(catSel.value));
  
  populateTrendSelect('all');
  
  sel.addEventListener('change', () => {
    drawTrendChart(sel.value);
  });
  
  // Draw first one
  if (sel.options.length > 0) drawTrendChart(sel.value);
}

function populateTrendSelect(cat) {
  const sel = document.getElementById('trend-select');
  sel.innerHTML = '';
  
  let names = Object.keys(trendsData).sort();
  if (cat !== 'all') {
    names = names.filter(n => trendsData[n][0].category === cat);
  }
  
  names.forEach(n => {
    const opt = document.createElement('option');
    opt.value = n; opt.textContent = n;
    sel.appendChild(opt);
  });
  
  if (names.length > 0) drawTrendChart(names[0]);
}

function openTrend(name) {
  document.querySelector('.nav-link[data-tab="trends"]').click();
  document.getElementById('trend-category').value = 'all';
  populateTrendSelect('all');
  document.getElementById('trend-select').value = name;
  drawTrendChart(name);
}

function drawTrendChart(name) {
  const data = trendsData[name];
  if (!data) return;
  
  document.getElementById('trend-chart-title').textContent = `${name} Trend`;
  
  const color = CAT_COLORS[data[0].category] || COLORS.accent;
  
  if (charts.trend) charts.trend.destroy();
  
  const ctx = document.getElementById('trendChart').getContext('2d');
  charts.trend = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map(d => {
        const date = new Date(d.timestamp);
        return `${date.getMonth()+1}/${date.getDate()} (${d.besu_ref})`;
      }),
      datasets: [{
        label: `Score (${data[0].score_unit})`,
        data: data.map(d => d.score),
        borderColor: color,
        backgroundColor: color + '20',
        borderWidth: 3,
        pointBackgroundColor: color,
        pointBorderColor: varBgCard(),
        pointBorderWidth: 2,
        pointRadius: 5,
        pointHoverRadius: 7,
        fill: true,
        tension: 0.1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const pt = data[ctx.dataIndex];
              return ` ${pt.score.toFixed(1)} ${pt.score_unit} (SHA: ${pt.besu_sha.substring(0,7)})`;
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: false,
          grid: { color: COLORS.border }
        },
        x: {
          grid: { display: false }
        }
      }
    }
  });
  
  // Render stats
  const cur = data[data.length-1].score;
  const min = Math.min(...data.map(d => d.score));
  const max = Math.max(...data.map(d => d.score));
  
  let pct = 0;
  if (data.length > 1) {
    const prev = data[0].score; // compare to first
    pct = ((cur - prev) / prev) * 100;
  }
  
  document.getElementById('trend-stats').innerHTML = `
    <div class="trend-stat">
      <div class="trend-stat-val">${cur.toFixed(1)}</div>
      <div class="trend-stat-lbl">Latest Score</div>
    </div>
    <div class="trend-stat">
      <div class="trend-stat-val">${max.toFixed(1)}</div>
      <div class="trend-stat-lbl">All-Time High</div>
    </div>
    <div class="trend-stat">
      <div class="trend-stat-val">${min.toFixed(1)}</div>
      <div class="trend-stat-lbl">All-Time Low</div>
    </div>
    <div class="trend-stat">
      <div class="trend-stat-val" style="color: ${pct >= 0 ? COLORS.green : COLORS.red}">
        ${pct > 0 ? '+' : ''}${pct.toFixed(1)}%
      </div>
      <div class="trend-stat-lbl">Overall Change</div>
    </div>
  `;
}

// ── Rendering: Runs Tab ──────────────────────────────────────────
function renderRunsTab() {
  const list = document.getElementById('runs-list');
  let html = '';
  
  indexData.runs.forEach(r => {
    const d = new Date(r.timestamp);
    const isError = r.ok < r.total;
    
    html += `
      <div class="run-item">
        <div class="run-dot ${isError ? 'error' : ''}"></div>
        <div class="run-meta">
          <div class="run-ref">${r.besu_ref} <span class="run-sha">${r.besu_sha.substring(0,7)}</span></div>
          <div class="run-ts">${d.toLocaleString()} · <span class="mono">${r.filename}</span></div>
        </div>
        <div class="run-type">${r.type}</div>
        <div class="run-count">${r.ok} / ${r.total} passed</div>
      </div>
    `;
  });
  
  list.innerHTML = html;
}

function varBgCard() {
  return getComputedStyle(document.documentElement).getPropertyValue('--bg-card').trim() || '#ffffff';
}
