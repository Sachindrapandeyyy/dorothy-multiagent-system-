/* ============================================================
   Dorothy OS v2.0 — App Controller
   Main application state, WebSocket, navigation, clock
   ============================================================ */

// ── App State ───────────────────────────────────────────────
export const appState = {
  currentPage: 'command-center',
  sidebarCollapsed: false,
  connected: false,
  ws: null,
  connections: {
    ollama: 'offline',
    cloud: 'offline',
    openclaw: 'offline'
  }
};

// ── DOM References ──────────────────────────────────────────
const shell = document.getElementById('app-shell');
const sidebar = document.getElementById('sidebar');
const navItems = document.querySelectorAll('.nav-item[data-page]');
const pageViews = document.querySelectorAll('.page-view');
const clockEl = document.getElementById('system-clock');
const ollamaDot = document.getElementById('dot-ollama');
const cloudDot = document.getElementById('dot-cloud');
const openclawDot = document.getElementById('dot-openclaw');

// ── Navigation ──────────────────────────────────────────────
function switchPage(pageId) {
  appState.currentPage = pageId;

  // Update nav active states
  navItems.forEach(item => {
    item.classList.toggle('active', item.dataset.page === pageId);
  });

  // Show/hide pages
  pageViews.forEach(view => {
    view.classList.toggle('active', view.id === `page-${pageId}`);
  });
}

navItems.forEach(item => {
  item.addEventListener('click', () => {
    const page = item.dataset.page;
    if (page) switchPage(page);
  });
});

// ── Sidebar Toggle ──────────────────────────────────────────
const toggleBtn = document.getElementById('btn-sidebar-toggle');
if (toggleBtn) {
  toggleBtn.addEventListener('click', () => {
    appState.sidebarCollapsed = !appState.sidebarCollapsed;
    shell.classList.toggle('sidebar-collapsed', appState.sidebarCollapsed);
  });
}

// ── System Clock ────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  const h = String(now.getHours()).padStart(2, '0');
  const m = String(now.getMinutes()).padStart(2, '0');
  const s = String(now.getSeconds()).padStart(2, '0');

  const months = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
  const day = String(now.getDate()).padStart(2, '0');
  const month = months[now.getMonth()];
  const year = now.getFullYear();

  if (clockEl) {
    clockEl.innerHTML = `
      <span class="clock-time">${h}</span><span class="clock-separator">:</span><span class="clock-time">${m}</span><span class="clock-separator">:</span><span class="clock-time">${s}</span>
      <span class="clock-date">${day} ${month} ${year}</span>
    `;
  }
}

updateClock();
setInterval(updateClock, 1000);

// ── Connection Status ───────────────────────────────────────
function setConnectionStatus(service, status) {
  appState.connections[service] = status;
  const dotMap = { ollama: ollamaDot, cloud: cloudDot, openclaw: openclawDot };
  const dot = dotMap[service];
  if (dot) {
    dot.className = 'status-dot ' + status;
  }
}

export { setConnectionStatus };

// ── WebSocket ───────────────────────────────────────────────
let reconnectTimer = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_DELAY = 30000;

function connectWebSocket() {
  setConnectionStatus('ollama', 'connecting');

  try {
    const ws = new WebSocket(`ws://${location.host}/ws`);

    ws.addEventListener('open', () => {
      appState.connected = true;
      appState.ws = ws;
      reconnectAttempts = 0;
      setConnectionStatus('ollama', 'online');
      console.log('[Dorothy] WebSocket connected');
    });

    ws.addEventListener('message', (event) => {
      try {
        const data = JSON.parse(event.data);
        handleWSMessage(data);
      } catch (e) {
        console.warn('[Dorothy] Non-JSON message:', event.data);
      }
    });

    ws.addEventListener('close', () => {
      appState.connected = false;
      appState.ws = null;
      setConnectionStatus('ollama', 'offline');
      console.log('[Dorothy] WebSocket disconnected');
      scheduleReconnect();
    });

    ws.addEventListener('error', () => {
      setConnectionStatus('ollama', 'error');
    });

  } catch (err) {
    console.warn('[Dorothy] WebSocket connection failed:', err.message);
    setConnectionStatus('ollama', 'offline');
    scheduleReconnect();
  }
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), MAX_RECONNECT_DELAY);
  reconnectAttempts++;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectWebSocket();
  }, delay);
}

function handleWSMessage(data) {
  // Handle init event for connection indicators
  if (data.type === 'init') {
    setConnectionStatus('cloud', data.data?.gemini ? 'online' : 'offline');
    setConnectionStatus('openclaw', data.data?.openclaw_status || 'offline');
  }

  // Handle live connection status updates
  if (data.type === 'connection_status') {
    const service = data.data?.service;
    const status = data.data?.status;
    if (service && status) {
      setConnectionStatus(service, status);
    }
  }

  // Dispatch to all modules via custom events
  window.dispatchEvent(new CustomEvent('dorothy:ws', { detail: data }));
}

export function sendWS(payload) {
  if (appState.ws && appState.ws.readyState === WebSocket.OPEN) {
    appState.ws.send(JSON.stringify(payload));
    return true;
  }
  console.warn('[Dorothy] WebSocket not connected, message dropped');
  return false;
}

// ── Window Controls (decorative in browser) ─────────────────
document.getElementById('btn-window-minimize')?.addEventListener('click', () => {
  console.log('[Dorothy] Minimize requested');
});
document.getElementById('btn-window-maximize')?.addEventListener('click', () => {
  console.log('[Dorothy] Maximize requested');
});
document.getElementById('btn-window-close')?.addEventListener('click', () => {
  if (confirm('Shut down Dorothy OS?')) {
    console.log('[Dorothy] Shutdown requested');
  }
});

// ── Model Gateway Selector Clicks ─────────────────────────
document.querySelectorAll('.llm-selector-item').forEach(item => {
  item.addEventListener('click', () => {
    const targetModel = item.getAttribute('data-model');
    if (targetModel) {
      console.log('[LLM Selector] Switch active provider request:', targetModel);
      sendWS({ type: 'command', data: { action: 'switch_model', model: targetModel } });
    }
  });
});

function updateModelSelectorUI(provider) {
  document.querySelectorAll('.llm-selector-item').forEach(el => {
    const modelAttr = el.getAttribute('data-model');
    const isTarget = modelAttr === provider;
    el.classList.toggle('active', isTarget);
    
    const indicator = el.querySelector('.llm-indicator');
    if (indicator) {
      indicator.textContent = isTarget ? '◈' : '◇';
    }
  });
}

// Listen for WebSocket broadcasts
window.addEventListener('dorothy:ws', (e) => {
  const msg = e.detail;
  if (msg.type === 'init' && msg.data) {
    const provider = msg.data.active_provider || 'auto';
    updateModelSelectorUI(provider);
  }
  if (msg.type === 'model_status' && msg.data) {
    const provider = msg.data.active_provider || 'auto';
    updateModelSelectorUI(provider);
  }
});

// ── Initialize ──────────────────────────────────────────────
switchPage('command-center');
connectWebSocket();

console.log('[Dorothy] OS v2.0 Command Center initialized');

