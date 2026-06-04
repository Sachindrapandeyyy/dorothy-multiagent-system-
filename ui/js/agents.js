/* ============================================================
   Dorothy OS v2.0 — Agents Module
   Agent cards, status updates from server
   ============================================================ */

import { sendWS } from './app.js';
import { addUserMessage, showThinking } from './chat.js';


// ── Default Agent Registry (overridden when server sends init) ──
let agents = [
  { id: 'lead',     name: 'Dorothy Lead',   role: 'Orchestrator',     status: 'idle', icon: '🧠' },
  { id: 'file',     name: 'File Agent',    role: 'File Operations',  status: 'idle', icon: '📁' },
  { id: 'system',   name: 'System Agent',  role: 'System Control',   status: 'idle', icon: '⚙️' },
  { id: 'desktop',  name: 'Desktop Agent', role: 'App Control',      status: 'idle', icon: '🖥️' },
  { id: 'browser',  name: 'Browser Agent', role: 'Web Automation',   status: 'idle', icon: '🌐' },
  { id: 'voice',    name: 'Voice Agent',   role: 'Speech Synthesis', status: 'idle', icon: '🔊' },
  { id: 'vision',   name: 'Vision Agent',  role: 'Object Detection', status: 'idle', icon: '👁️' },
  { id: 'research', name: 'Research Agent', role: 'Data & APIs',     status: 'idle', icon: '🔬' },
  { id: 'backend',  name: 'Backend Agent', role: 'Data & Security',   status: 'idle', icon: '⚙️' },
  { id: 'security', name: 'Security Agent', role: 'Credentials Gate', status: 'idle', icon: '🛡️' },
  { id: 'windows',  name: 'Windows Agent',  role: 'OS Controller',     status: 'idle', icon: '🖥️' },
];

// ── DOM ─────────────────────────────────────────────────────
const agentGrid = document.getElementById('agent-grid');
const agentCountBadge = document.querySelector('#agent-status-panel .badge');

// ── Render Agent Cards ──────────────────────────────────────
function renderAgentCards() {
  if (!agentGrid) return;
  agentGrid.innerHTML = '';

  agents.forEach(agent => {
    // Skip lead agent in status cards as it is rendered in the compiled LangGraph flowchart node
    if (agent.id === 'lead') return;

    const card = document.createElement('div');
    card.className = `hud-agent-card ${agent.status === 'working' ? 'working' : ''}`;
    card.id = `agent-card-${agent.id}`;
    card.innerHTML = `
      <span class="hud-agent-icon">${agent.icon}</span>
      <span>${agent.name.split(' ')[0]}</span>
    `;
    agentGrid.appendChild(card);
  });

  // Update badge count
  if (agentCountBadge) {
    agentCountBadge.textContent = `${agents.length - 1} ACTIVE`;
  }
}

// ── Public API ──────────────────────────────────────────────

export function updateAgentStatus(agentId, status) {
  const agent = agents.find(a => a.id === agentId);
  if (!agent) return;

  agent.status = status;
  const dot = document.getElementById(`agent-dot-${agentId}`);
  if (dot) {
    dot.className = `agent-status-dot ${status}`;
  }

  // Update widescreen HUD traditional cards
  const card = document.getElementById(`agent-card-${agentId}`);
  if (card) {
    card.className = `hud-agent-card ${status === 'working' ? 'working' : ''}`;
  }

  // Update compiled LangGraph flowchart diagram nodes
  const graphNode = document.getElementById(`graph-node-${agentId}`);
  if (graphNode) {
    if (status === 'working' || status === 'thinking' || status === 'success') {
      graphNode.classList.add('active');
      const sub = graphNode.querySelector('.node-subtext');
      if (sub) sub.textContent = status.toUpperCase();
    } else {
      graphNode.classList.remove('active');
      const sub = graphNode.querySelector('.node-subtext');
      if (sub) sub.textContent = 'IDLE';
    }
  }
}

function getStatusColor(status) {
  switch (status) {
    case 'working':  return 'rgba(0, 194, 255, 0.5)';
    case 'thinking': return 'rgba(255, 184, 0, 0.5)';
    case 'error':    return 'rgba(255, 59, 59, 0.5)';
    case 'success':  return 'rgba(0, 255, 136, 0.5)';
    default:         return 'rgba(136, 146, 160, 0.1)';
  }
}

// ── Listen for WebSocket agent updates ──────────────────────
// Server sends: {type: "agent_status", data: {agents: [...]}}
// and also: {type: "init", data: {agents: [...]}}
window.addEventListener('dorothy:ws', (e) => {
  const msg = e.detail;

  if (msg.type === 'init' && msg.data?.agents) {
    // Server sent initial agent list — use it
    agents = msg.data.agents.map(a => ({
      id: a.id,
      name: a.name,
      role: a.role,
      icon: a.icon || '🤖',
      status: a.status || 'idle',
    }));
    renderAgentCards();
  }

  if (msg.type === 'agent_status' && msg.data?.agents) {
    // Server sent full agent list update
    msg.data.agents.forEach(serverAgent => {
      const local = agents.find(a => a.id === serverAgent.id || a.role === serverAgent.role);
      if (local && local.status !== serverAgent.status) {
        updateAgentStatus(local.id, serverAgent.status);
      }
    });
  }
});

// ── Initialize ──────────────────────────────────────────────
renderAgentCards();

// ── Direct Agent Dispatch Modal ─────────────────────────────
const dispatchModal = document.getElementById('modal-agent-dispatch');
const dispatchTargetBadge = document.getElementById('dispatch-target-badge');
const dispatchPromptInput = document.getElementById('dispatch-prompt-input');
const dispatchCloseBtn = document.getElementById('btn-close-dispatch');
const dispatchSendBtn = document.getElementById('btn-dispatch-send');

let activeDispatchAgentId = '';

function openAgentDispatch(agentId) {
  if (!dispatchModal || !dispatchTargetBadge) return;
  activeDispatchAgentId = agentId;
  
  dispatchTargetBadge.textContent = agentId.toUpperCase();
  dispatchPromptInput.value = '';
  
  dispatchModal.classList.add('active');
  dispatchPromptInput.focus();
}

function closeAgentDispatch() {
  if (!dispatchModal) return;
  dispatchModal.classList.remove('active');
  activeDispatchAgentId = '';
}

// Bind click handlers to flowchart nodes to trigger direct dispatches
document.querySelectorAll('.graph-node').forEach(node => {
  node.addEventListener('click', () => {
    const parts = node.id.split('graph-node-');
    if (parts.length > 1) {
      const agentId = parts[1];
      console.log(`[Agent Dispatch] Selecting node: ${agentId}`);
      openAgentDispatch(agentId);
    }
  });
});

dispatchCloseBtn?.addEventListener('click', closeAgentDispatch);

dispatchModal?.addEventListener('click', (e) => {
  if (e.target === dispatchModal) {
    closeAgentDispatch();
  }
});

// Submit direct agent query bypass pipeline
dispatchSendBtn?.addEventListener('click', () => {
  const promptText = dispatchPromptInput.value.trim();
  if (!promptText || !activeDispatchAgentId) return;

  const command = `[DIRECT AGENT DISPATCH -> ${activeDispatchAgentId.toUpperCase()}]: ${promptText}`;
  
  closeAgentDispatch();

  addUserMessage(command);
  showThinking();

  sendWS({ type: 'chat_message', data: { message: command } });
});

