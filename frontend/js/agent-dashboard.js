/**
 * AgentDashboard Class
 * Coordinates rendering active agent status cards (idle/working/error) and
 * keeps a rolling historical trace logs of AI actions, file triggers, and system diagnostic tasks.
 */
class AgentDashboard {
  constructor(agentsContainerId, logContainerId) {
    this.agentsContainer = document.getElementById(agentsContainerId);
    this.logContainer = document.getElementById(logContainerId);
    this.maxLogEntries = 60;
  }

  /**
   * Re-build and render all active agent cards in grid panel
   * @param {Array} agents - List of subagents (name, role, status, icon)
   */
  updateAgents(agents) {
    if (!this.agentsContainer || !agents) return;

    // Build complete card HTML safely
    let html = '';
    agents.forEach(agent => {
      const icon = agent.icon || '🤖';
      const name = agent.name || 'AI Worker';
      const role = agent.role || 'Sub-Routine';
      const status = agent.status || 'idle'; // idle, working, error
      
      let statusDotClass = 'idle';
      if (status === 'working' || status === 'active') {
        statusDotClass = 'working';
      } else if (status === 'error' || status === 'failed') {
        statusDotClass = 'error';
      }

      html += `
        <div class="agent-card">
          <div class="agent-icon">${icon}</div>
          <div class="agent-info">
            <div class="agent-name">${name}</div>
            <div class="agent-role">${role}</div>
          </div>
          <div class="agent-status-indicator">
            <span class="agent-status-dot ${statusDotClass}"></span>
            <span>${status}</span>
          </div>
        </div>
      `;
    });

    this.agentsContainer.innerHTML = html;
  }

  /**
   * Log standard activities, system metrics warnings, or workspace creations.
   * @param {string} text - Action description
   * @param {string} agentName - Name of trigger source
   * @param {string} timestamp - (Optional) Timestamp format
   */
  addActivity(text, agentName = 'SYSTEM', timestamp = null) {
    if (!this.logContainer) return;

    const time = timestamp ? timestamp : new Date().toTimeString().split(' ')[0];
    
    // Create element
    const entry = document.createElement('div');
    entry.className = 'activity-entry';
    
    // Highlight SYSTEM as orange-yellow accent
    const agentDisplay = agentName.toUpperCase();
    const isSystem = agentDisplay === 'SYSTEM' || agentDisplay === 'CORE';
    const agentColorStyle = isSystem ? 'color: var(--hud-amber);' : 'color: var(--hud-orange);';

    entry.innerHTML = `
      <div class="activity-meta">
        <span class="activity-time">[${time}]</span>
        <span class="activity-agent" style="${agentColorStyle}">${agentDisplay}</span>
      </div>
      <div class="activity-text">${text}</div>
    `;

    // Append to container
    this.logContainer.appendChild(entry);

    // Limit active elements in DOM to preserve performance
    while (this.logContainer.children.length > this.maxLogEntries) {
      this.logContainer.removeChild(this.logContainer.firstChild);
    }

    // Auto-scroll logs
    this.logContainer.scrollTop = this.logContainer.scrollHeight;
  }
}
