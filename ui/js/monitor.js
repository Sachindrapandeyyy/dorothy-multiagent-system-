/* ============================================================
   Dorothy OS v2.0 — System Monitor Module
   CPU, RAM, Disk, Battery gauges with smooth radial circle support
   ============================================================ */

import { sendWS } from './app.js';


const CIRCUMFERENCE = 251.2; // 2 * PI * r (r=40)

// ── DOM ─────────────────────────────────────────────────────
const statBars = {
  cpu:     { fill: document.getElementById('bar-cpu'),     value: document.getElementById('val-cpu') },
  ram:     { fill: document.getElementById('bar-ram'),     value: document.getElementById('val-ram') },
  disk:    { fill: document.getElementById('bar-disk'),    value: document.getElementById('val-disk') },
  gpu:     { fill: document.getElementById('bar-gpu'),     value: document.getElementById('val-gpu') },
  battery: { fill: document.getElementById('bar-battery'), value: document.getElementById('val-battery') },
};

// ── Update a single stat ────────────────────────────────────
function updateBar(key, percent) {
  const clamped = Math.max(0, Math.min(100, Math.round(percent)));

  // Update traditional progress bars if they exist
  const bar = statBars[key];
  if (bar && bar.fill && bar.value) {
    bar.fill.style.width = clamped + '%';
    bar.value.textContent = clamped + '%';
    bar.fill.classList.remove('level-ok', 'level-warn', 'level-crit');
    if (clamped < 60) {
      bar.fill.classList.add('level-ok');
    } else if (clamped < 85) {
      bar.fill.classList.add('level-warn');
    } else {
      bar.fill.classList.add('level-crit');
    }
  }

  // Update widescreen HUD circular gauges if they exist
  const circle = document.getElementById(`circle-${key}`);
  const valText = document.getElementById(`val-${key}`);
  
  if (circle) {
    const offset = CIRCUMFERENCE - (clamped / 100) * CIRCUMFERENCE;
    circle.style.strokeDashoffset = offset;
  }
  
  if (valText) {
    valText.textContent = clamped + '%';
  }
}

// ── Public API ──────────────────────────────────────────────

export function updateSystemStats(stats) {
  if (!stats) return;

  // CPU is top-level
  if (stats.cpu !== undefined) updateBar('cpu', stats.cpu);

  // RAM is nested: {percent, used_gb, total_gb}
  if (stats.ram?.percent !== undefined) updateBar('ram', stats.ram.percent);

  // Disk is array — take first partition's percent
  if (Array.isArray(stats.disk) && stats.disk.length > 0) {
    updateBar('disk', stats.disk[0].percent || 0);
  }

  // GPU is top-level
  if (stats.gpu !== undefined) {
    updateBar('gpu', stats.gpu);
  } else {
    // Fallback static value or small mock if GPU isn't active on local device
    updateBar('gpu', 30);
  }

  // Battery is nested
  if (stats.battery?.percent !== undefined) updateBar('battery', stats.battery.percent);
}

// ── Listen for WebSocket updates ────────────────────────────
window.addEventListener('dorothy:ws', (e) => {
  const msg = e.detail;
  if (msg.type === 'system_stats') {
    updateSystemStats(msg.data);
  }
  if (msg.type === 'processes_list' && msg.data) {
    renderProcessRows(msg.data.processes);
  }
  if (msg.type === 'kill_process_result' && msg.data) {
    const res = msg.data;
    if (res.success) {
      console.log('[Task Manager]', res.message);
      queryProcesses(); // Immediate refresh
    } else {
      alert(`Error terminating process: ${res.error}`);
      queryProcesses();
    }
  }
});

// ── Process Task Manager Modal Control ───────────────────────
const modalOverlay = document.getElementById('modal-task-manager');
const tableBody = document.getElementById('process-list-table-body');
const closeBtn = document.getElementById('btn-close-taskmgr');

let isModalOpen = false;
let processPollInterval = null;

function openTaskManager() {
  if (!modalOverlay) return;
  modalOverlay.classList.add('active');
  isModalOpen = true;
  
  queryProcesses();
  
  // Refresh task manager listing every 3 seconds when open
  processPollInterval = setInterval(queryProcesses, 3000);
}

function closeTaskManager() {
  if (!modalOverlay) return;
  modalOverlay.classList.remove('active');
  isModalOpen = false;
  
  if (processPollInterval) {
    clearInterval(processPollInterval);
    processPollInterval = null;
  }
}

function queryProcesses() {
  if (!isModalOpen) return;
  sendWS({ type: 'command', data: { action: 'get_processes' } });
}

// Bind CPU/RAM/GPU/DISK/BATT circular gauges to trigger task manager modal
document.querySelectorAll('.radial-gauge-container').forEach(gauge => {
  gauge.addEventListener('click', () => {
    openTaskManager();
  });
});

closeBtn?.addEventListener('click', closeTaskManager);

modalOverlay?.addEventListener('click', (e) => {
  if (e.target === modalOverlay) {
    closeTaskManager();
  }
});

function renderProcessRows(processes) {
  if (!tableBody) return;
  tableBody.innerHTML = '';

  if (!processes || processes.length === 0) {
    tableBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: var(--space-md);">No active processes found.</td></tr>`;
    return;
  }

  processes.forEach(proc => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${proc.pid}</td>
      <td style="color:#ffffff; font-weight:bold;">${escapeHtml(proc.name)}</td>
      <td style="color: ${proc.cpu_percent > 40 ? '#ff3b3b' : 'var(--color-accent-cyan)'}; font-weight: bold;">${proc.cpu_percent}%</td>
      <td>${proc.memory_mb} MB</td>
      <td>
        <button class="btn-process-kill" data-pid="${proc.pid}">KILL</button>
      </td>
    `;
    tableBody.appendChild(tr);
  });

  // Bind process kill triggers
  tableBody.querySelectorAll('.btn-process-kill').forEach(btn => {
    btn.addEventListener('click', () => {
      const pid = btn.getAttribute('data-pid');
      btn.textContent = 'KILLING...';
      btn.disabled = true;
      sendWS({ type: 'command', data: { action: 'kill_process', pid: parseInt(pid) } });
    });
  });
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

