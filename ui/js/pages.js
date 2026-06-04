/* ============================================================
   Dorothy OS v2.0 — Pages Module
   Wires up live data for all sidebar pages.
   ============================================================ */

// Use window event bus to send WS messages (no import needed)
function sendWS(obj) {
  window.dispatchEvent(new CustomEvent('dorothy:send', { detail: obj }));
}


let headQueryCount    = 0;
let headDispatchCount = 0;

// ── Listen for WS events ─────────────────────────────────────
window.addEventListener('dorothy:ws', (e) => {
  const data = e.detail;

  // Agent status updates → Agent Dashboard
  if (data.type === 'agent_status') {
    const agents = data.data?.agents || [];
    updateAgentDashboard(agents);
  }

  // System stats → System Monitor + update head stat counters
  if (data.type === 'system_stats') {
    updateSysmonPage(data.data);
  }

  // Cognitive log → dispatch log + head agent counter
  if (data.type === 'cognitive_log') {
    const log = data.content || '';
    appendDispatchLog(log);
    if (log.includes('[HEAD]')) {
      headQueryCount++;
      const el = document.getElementById('head-queries');
      if (el) el.textContent = headQueryCount;
    }
    if (log.includes('dispatching') || log.includes('BACKGROUND')) {
      headDispatchCount++;
      const el = document.getElementById('head-dispatches');
      if (el) el.textContent = headDispatchCount;
    }
  }

  // Health check / init
  if (data.type === 'init') {
    updateSecurityKeyStatus(data.data);
  }
});

// ── Agent Dashboard ──────────────────────────────────────────

function updateAgentDashboard(agents) {
  const headEl = document.getElementById('head-status-text');
  const headDot = document.getElementById('head-live-dot');

  for (const agent of agents) {
    const id = agent.id || '';
    const status = agent.status || 'idle';

    // Head agent
    if (id === 'lead') {
      if (headEl) {
        headEl.textContent = status.toUpperCase();
        headEl.style.color = status === 'idle' ? '#00ff88' : status === 'thinking' ? '#ffb800' : '#00c2ff';
      }
      if (headDot) {
        headDot.style.background = status === 'idle' ? '#00ff88' : '#ffb800';
      }
      continue;
    }

    // Employee agent cards
    const statusEl = document.getElementById(`emp-status-${id}`);
    const cardEl = document.getElementById(`emp-${id}`);
    if (statusEl) {
      statusEl.textContent = status.toUpperCase();
      statusEl.className = `emp-status ${status}`;
    }
    if (cardEl) {
      cardEl.className = `emp-card ${status !== 'idle' ? 'emp-active' : ''}`;
    }
  }
}

function appendDispatchLog(log) {
  const feed = document.getElementById('task-log-feed');
  if (!feed) return;
  const row = document.createElement('div');
  row.className = 'task-log-row';
  const time = new Date().toLocaleTimeString('en-IN', { hour12: false });
  row.innerHTML = `<span class="tlog-time">${time}</span><span class="tlog-msg">${escapeHtml(log)}</span>`;
  feed.appendChild(row);
  // Keep only last 60 entries
  while (feed.children.length > 60) feed.removeChild(feed.firstChild);
  feed.scrollTop = feed.scrollHeight;
}

// ── Memory Center ────────────────────────────────────────────

document.getElementById('memory-search-btn')?.addEventListener('click', doMemorySearch);
document.getElementById('memory-search-input')?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') doMemorySearch();
});

async function doMemorySearch() {
  const query = document.getElementById('memory-search-input')?.value?.trim();
  const panel = document.getElementById('memory-results-panel');
  if (!query || !panel) return;

  panel.innerHTML = '<div class="memory-result-placeholder">🔍 Searching...</div>';

  try {
    const res = await fetch(`/api/memory/search?q=${encodeURIComponent(query)}&limit=10`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderMemoryResults(data.results || [], panel);
  } catch (err) {
    panel.innerHTML = `<div class="memory-result-placeholder" style="color:#ff4444;">Search failed: ${err.message}</div>`;
  }
}

function renderMemoryResults(results, panel) {
  if (!results.length) {
    panel.innerHTML = '<div class="memory-result-placeholder">No memories found for that query.</div>';
    return;
  }
  panel.innerHTML = results.map(r => `
    <div class="memory-result-card">
      <div class="mem-res-role ${r.role}">${(r.role || 'unknown').toUpperCase()}</div>
      <div class="mem-res-text">${escapeHtml(r.text || '')}</div>
      <div class="mem-res-meta">${(r.timestamp || '').replace('T', ' ').slice(0, 19)}</div>
    </div>
  `).join('');
}

// Load memory stats on page activation
async function loadMemoryStats() {
  try {
    const res = await fetch('/api/memory/stats');
    if (!res.ok) return;
    const data = await res.json();
    const el = (id) => document.getElementById(id);
    if (el('mem-total-docs')) el('mem-total-docs').textContent = data.total || '—';
    if (el('mem-user-msgs')) el('mem-user-msgs').textContent = data.user_count || '—';
    if (el('mem-ai-msgs'))   el('mem-ai-msgs').textContent   = data.ai_count   || '—';
  } catch {}
}

// ── System Monitor ───────────────────────────────────────────

function updateSysmonPage(stats) {
  const setBar = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.style.width = `${Math.min(100, val || 0)}%`;
  };
  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };

  setBar('smon-bar-cpu',  stats.cpu_percent);   setVal('smon-val-cpu',  `${stats.cpu_percent ?? '—'}%`);
  setBar('smon-bar-ram',  stats.ram_percent);   setVal('smon-val-ram',  `${stats.ram_percent ?? '—'}%`);
  setBar('smon-bar-disk', stats.disk_percent);  setVal('smon-val-disk', `${stats.disk_percent ?? '—'}%`);
  setBar('smon-bar-batt', stats.battery ?? 100);setVal('smon-val-batt', `${stats.battery ?? '—'}%`);

  const dl = stats.net_recv_mb ?? '—';
  const ul = stats.net_sent_mb ?? '—';
  setVal('smon-net-down', `${dl} MB/s`);
  setVal('smon-net-up',   `${ul} MB/s`);
  setVal('smon-val-net',  `${dl}`);

  // Ollama status from health
  const ollamaEl = document.getElementById('smon-ollama-status');
  if (ollamaEl) ollamaEl.textContent = stats.ollama_ok ? '🟢 ONLINE' : '🔴 OFFLINE';
}

// Process table refresh
document.getElementById('btn-refresh-procs')?.addEventListener('click', loadProcessTable);

async function loadProcessTable() {
  const tbody = document.getElementById('smon-proc-tbody');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="5" class="smon-loading">Refreshing...</td></tr>';
  try {
    sendWS({ type: 'command', data: { action: 'get_processes' } });
  } catch {}
}

window.addEventListener('dorothy:ws', (e) => {
  const data = e.detail;
  if (data.type === 'processes_list') {
    const procs = data.data?.processes || [];
    const tbody = document.getElementById('smon-proc-tbody');
    if (!tbody) return;
    tbody.innerHTML = procs.map(p => `
      <tr>
        <td>${p.pid}</td>
        <td class="smon-proc-name">${escapeHtml(p.name || '')}</td>
        <td style="color:#00c2ff;">${(p.cpu_percent ?? 0).toFixed(1)}%</td>
        <td style="color:#00ff88;">${(p.memory_percent ?? 0).toFixed(1)}%</td>
        <td><button class="smon-kill-btn" onclick="killProc(${p.pid})">Kill</button></td>
      </tr>
    `).join('') || '<tr><td colspan="5" class="smon-loading">No processes</td></tr>';
  }
});

window.killProc = function(pid) {
  if (confirm(`Kill PID ${pid}?`)) {
    sendWS({ type: 'command', data: { action: 'kill_process', pid } });
  }
};

// ── Security Center ──────────────────────────────────────────

document.getElementById('sec-bio-challenge-btn')?.addEventListener('click', () => {
  sendWS({ type: 'command', data: { action: 'trigger_biometrics' } });
  const s = document.getElementById('sec-bio-status');
  if (s) { s.textContent = 'WIN_HELLO: CHALLENGING...'; s.style.color = '#ffb800'; }
});

window.addEventListener('dorothy:ws', (e) => {
  const data = e.detail;
  if (data.type === 'biometric_status') {
    const s = document.getElementById('sec-bio-status');
    const granted = data.data?.status === 'GRANTED';
    if (s) {
      s.textContent = granted ? 'WIN_HELLO: GRANTED ✅' : 'WIN_HELLO: REFUSED ❌';
      s.style.color = granted ? '#00ff88' : '#ff4444';
    }
    addSecAuditRow(granted ? 'BIO_CHALLENGE' : 'BIO_REFUSED', granted ? 'ok' : 'fail');
  }
});

function addSecAuditRow(action, tagClass) {
  const feed = document.getElementById('sec-audit-feed');
  if (!feed) return;
  const time = new Date().toLocaleTimeString('en-IN', { hour12: false });
  const row = document.createElement('div');
  row.className = 'sec-audit-row';
  row.innerHTML = `<span class="sec-audit-time">${time}</span><span class="sec-audit-action">${action}</span><span class="sec-audit-tag ${tagClass}">${tagClass === 'ok' ? 'VALID' : 'DENIED'}</span>`;
  feed.insertBefore(row, feed.firstChild);
}

function updateSecurityKeyStatus(initData) {
  const set = (id, ok) => {
    const el = document.getElementById(id);
    if (el) { el.textContent = ok ? '🟢 Configured' : '🔴 Missing'; el.style.color = ok ? '#00ff88' : '#ff4444'; }
  };
  set('sec-key-gemini',  initData?.gemini);
  set('sec-key-claude',  initData?.claude_configured);
  set('sec-key-ollama',  initData?.ollama_connected);
  set('sec-key-openclaw', initData?.openclaw_status === 'online');
}

// Check health endpoint for key status
async function checkSecurityKeys() {
  try {
    const res = await fetch('/api/health');
    if (!res.ok) return;
    const d = await res.json();
    const set = (id, ok) => {
      const el = document.getElementById(id);
      if (el) { el.textContent = ok ? '🟢 Online' : '🔴 Offline'; el.style.color = ok ? '#00ff88' : '#ff4444'; }
    };
    set('sec-key-gemini',   d.gemini_configured);
    set('sec-key-claude',   d.gemini_configured); // proxy indicator
    set('sec-key-ollama',   d.ollama_connected);
    set('sec-key-openclaw', false);
  } catch {}
}

// ── Settings Page ────────────────────────────────────────────

// Load Ollama models into selector
async function loadOllamaModels() {
  const sel = document.getElementById('set-ollama-model');
  if (!sel) return;
  try {
    const res = await fetch('/api/models');
    const data = await res.json();
    const models = data.models || [];
    if (models.length) {
      sel.innerHTML = models.map(m => `<option value="${m}">${m}</option>`).join('');
    }
  } catch {
    sel.innerHTML = '<option>Could not load models</option>';
  }
}

document.getElementById('set-apply-model')?.addEventListener('click', () => {
  const provider = document.getElementById('set-provider')?.value;
  const model    = document.getElementById('set-ollama-model')?.value;
  if (provider && provider !== 'ollama') {
    sendWS({ type: 'command', data: { action: 'switch_model', model: provider } });
  } else if (model) {
    sendWS({ type: 'command', data: { action: 'switch_model', model } });
  }
  showSettingsFeedback('set-apply-model', '✅ Applied');
});

document.getElementById('set-apply-conn')?.addEventListener('click', async () => {
  const result = document.getElementById('set-conn-result');
  if (result) result.textContent = 'Testing...';
  try {
    const res = await fetch('/api/health');
    const d = await res.json();
    if (result) {
      result.textContent = `Ollama: ${d.ollama_connected ? '✅' : '❌'}  Gemini: ${d.gemini_configured ? '✅' : '❌'}`;
      result.style.color = '#00ff88';
    }
  } catch (e) {
    if (result) { result.textContent = `❌ Connection failed: ${e.message}`; result.style.color = '#ff4444'; }
  }
});

// Theme color swatches
document.querySelectorAll('.color-swatch').forEach(swatch => {
  swatch.addEventListener('click', () => {
    document.querySelectorAll('.color-swatch').forEach(s => s.classList.remove('active'));
    swatch.classList.add('active');
    const color = swatch.dataset.color;
    document.documentElement.style.setProperty('--color-accent-cyan', color);
  });
});

function showSettingsFeedback(btnId, msg) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  const orig = btn.textContent;
  btn.textContent = msg;
  setTimeout(() => { btn.textContent = orig; }, 2000);
}

// ── Page Activation Hooks ────────────────────────────────────

// Run when user switches to a page
const pageObserver = new MutationObserver(() => {
  if (document.getElementById('page-system-monitor')?.classList.contains('active')) {
    loadProcessTable();
  }
  if (document.getElementById('page-memory-center')?.classList.contains('active')) {
    loadMemoryStats();
  }
  if (document.getElementById('page-security-center')?.classList.contains('active')) {
    checkSecurityKeys();
  }
  if (document.getElementById('page-settings')?.classList.contains('active')) {
    loadOllamaModels();
  }
});

document.querySelectorAll('.page-view').forEach(page => {
  pageObserver.observe(page, { attributes: true, attributeFilter: ['class'] });
});

// ── Utility ──────────────────────────────────────────────────
function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

// Boot
loadOllamaModels();
checkSecurityKeys();
