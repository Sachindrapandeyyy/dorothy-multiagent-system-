/* ============================================================
   Dorothy OS v2.0 — Cognitive Log Module
   Monospace timestamped log feed with color-coded tags
   Connected to real server cognitive_log events
   ============================================================ */

// ── Config ──────────────────────────────────────────────────
const MAX_ENTRIES = 100;

// ── DOM ─────────────────────────────────────────────────────
const logList = document.getElementById('cognitive-log-list');
let entryCount = 0;

// ── Public API ──────────────────────────────────────────────

export function addCognitiveLog(message, type = 'cognitive') {
  if (!logList) return;

  const entry = document.createElement('div');
  entry.className = `log-entry ${type}`;

  const now = new Date();
  const ts = [
    String(now.getHours()).padStart(2, '0'),
    String(now.getMinutes()).padStart(2, '0'),
    String(now.getSeconds()).padStart(2, '0'),
  ].join(':');

  const ms = String(now.getMilliseconds()).padStart(3, '0');

  const tagMap = {
    cognitive: 'COGNITIVE',
    error:     'ERROR',
    system:    'SYSTEM',
    success:   'SUCCESS',
  };

  const tagLabel = tagMap[type] || type.toUpperCase();

  entry.innerHTML = `<span class="log-timestamp">${ts}.${ms}</span><span class="log-tag">[${tagLabel}]</span> <span class="log-message">${escapeHtml(message)}</span>`;

  logList.appendChild(entry);
  entryCount++;

  // Trim old entries
  while (entryCount > MAX_ENTRIES && logList.firstChild) {
    logList.removeChild(logList.firstChild);
    entryCount--;
  }

  // Auto-scroll
  logList.scrollTop = logList.scrollHeight;
}

function escapeHtml(str) {
  const el = document.createElement('span');
  el.textContent = str;
  return el.innerHTML;
}

// ── Classify cognitive_log content ──────────────────────────
function classifyLogType(content) {
  if (!content) return 'system';
  const lower = content.toLowerCase();
  if (lower.includes('[error]') || lower.includes('error') || lower.includes('failed')) return 'error';
  if (lower.includes('[success]') || lower.includes('complete') || lower.includes('success')) return 'success';
  if (lower.includes('[cognitive]') || lower.includes('routing') || lower.includes('context')) return 'cognitive';
  return 'system';
}

// ── Clean tag prefixes from message ─────────────────────────
function cleanMessage(content) {
  return content
    .replace(/^\[COGNITIVE\]\s*/i, '')
    .replace(/^\[SYSTEM\]\s*/i, '')
    .replace(/^\[ERROR\]\s*/i, '')
    .replace(/^\[SUCCESS\]\s*/i, '');
}

// ── Listen for WebSocket log events ─────────────────────────
// Server sends: {type: "cognitive_log", content: "[COGNITIVE] ...message..."}
window.addEventListener('dorothy:ws', (e) => {
  const msg = e.detail;

  if (msg.type === 'cognitive_log') {
    const content = msg.content || msg.data?.content || '';
    const type = classifyLogType(content);
    addCognitiveLog(cleanMessage(content), type);
  }

  // Also log init events
  if (msg.type === 'init') {
    addCognitiveLog('Command Center connected to Dorothy OS backend', 'success');
    if (msg.data?.gemini) {
      addCognitiveLog('Gemini Cloud API configured and available', 'system');
    }
    addCognitiveLog(`Model loaded: ${msg.data?.model || 'unknown'}`, 'system');
    addCognitiveLog(`${msg.data?.agents?.length || 0} agents registered in swarm`, 'cognitive');
  }
});

// ── Initial boot message ────────────────────────────────────
addCognitiveLog('Cognitive log feed initialized', 'system');
