/**
 * Main Orchestrator (app.js)
 * Manages the cinematic holographic boot sequence, instantiates all HUD elements,
 * connects websocket signals to visual state changes, handles clock updates,
 * and processes outgoing command arrays.
 */
document.addEventListener('DOMContentLoaded', () => {
  // Start cinematic loader
  runBootSequence();
});

// Global instances holder
let particles = null;
let arcReactor = null;
let neuralNetwork = null;
let systemMonitor = null;
let chatManager = null;
let agentDashboard = null;
let audioViz = null;
let socket = null;
let activeStream = null;
let globe = null;


// Mock initial agent list to guarantee stunning visuals immediately on bootup
const INITIAL_AGENTS = [
  { name: "JARVIS Lead", role: "Orchestrator", status: "idle", icon: "🎯" },
  { name: "Cyber Sentry", role: "Firewall Guard", status: "working", icon: "🛡️" },
  { name: "Code Smith", role: "Synthesis Unit", status: "idle", icon: "💻" },
  { name: "Data Architect", role: "Knowledge Graph", status: "idle", icon: "🧠" }
];

/**
 * Animated Cinematic Hologram Loading Screen
 */
function runBootSequence() {
  const bootOverlay = document.getElementById('boot-overlay');
  const bootBar = document.getElementById('boot-bar');
  const bootPercent = document.getElementById('boot-percent');
  const bootStatusLabel = document.getElementById('boot-status-label');
  const bootConsole = document.getElementById('boot-console');

  const logLines = [
    "INITIALIZING CORE SYSTEM HULL CONTROLLER...",
    "ESTABLISHING SECURE THERMAL CHANNEL CORES...",
    "LAUNCHING INTERACTIVE PARTICLE FIELD MATRICES...",
    "CALIBRATING ROTATING ARC STABILIZERS...",
    "SYNCHRONIZING NEURAL LAYER NODES [5, 8, 6, 4, 2]...",
    "CONNECTING TELEMETRY PORTS RX/TX...",
    "DECRYPTING SECURE CHAT SYNAPSE GATEWAY...",
    "SYSTEM SECURED. WELL-DONE SIR. JARVIS LOGGED IN."
  ];

  let progress = 0;
  let logIndex = 0;

  const consoleInterval = setInterval(() => {
    if (logIndex < logLines.length) {
      const line = document.createElement('div');
      line.innerText = `> ${logLines[logIndex]}`;
      bootConsole.appendChild(line);
      bootConsole.scrollTop = bootConsole.scrollHeight;
      
      // Update label with current task
      bootStatusLabel.innerText = logLines[logIndex].toLowerCase();
      logIndex++;
    }
  }, 350);

  const progressInterval = setInterval(() => {
    // Variable progress speed
    progress += Math.floor(Math.random() * 8) + 2;
    if (progress >= 100) {
      progress = 100;
      clearInterval(progressInterval);
      clearInterval(consoleInterval);

      // Print final line if not printed
      if (logIndex < logLines.length) {
        const line = document.createElement('div');
        line.innerText = `> ${logLines[logLines.length - 1]}`;
        bootConsole.appendChild(line);
      }

      bootStatusLabel.innerText = "boot validation completed successfully.";
      bootPercent.innerText = "100%";
      bootBar.style.width = "100%";

      // Play subtle digital sound or fade out overlay
      setTimeout(() => {
        bootOverlay.style.transition = "opacity 0.6s cubic-bezier(0.25, 0.8, 0.25, 1)";
        bootOverlay.style.opacity = 0;
        
        setTimeout(() => {
          bootOverlay.style.display = "none";
          // Initialize core components inside dashboard
          initHUD();
        }, 600);
      }, 500);
    } else {
      bootPercent.innerText = `${progress}%`;
      bootBar.style.width = `${progress}%`;
    }
  }, 120);
}

/**
 * Initialize all subsystems
 */
function initHUD() {
  console.log("[Core] Initializing visual assets and connection listeners...");

  // 1. Particle field
  particles = new ParticleSystem('particle-canvas');

  // 2. Arc Reactor Canvas
  arcReactor = new ArcReactor('arc-reactor-canvas');

  // 3. Neural Synapses Grid Canvas
  neuralNetwork = new NeuralNetwork('neural-canvas');

  // 4. Circular Resource telemetry gauges
  systemMonitor = new SystemMonitor();

  // 5. Scrollable chat manager bubbles
  chatManager = new ChatManager(
    'chat-messages',
    'chat-user-input',
    'chat-send-btn',
    'chat-mic-btn',
    'chat-typing'
  );

  // 6. Agents and operations board logs
  agentDashboard = new AgentDashboard('agents-list', 'activity-log');
  agentDashboard.updateAgents(INITIAL_AGENTS);
  agentDashboard.addActivity("Tactical HUD initialization completed.", "SYSTEM");

  // 7. Audio wave capsules visualizer footer
  audioViz = new AudioVisualizer('waveform-canvas');

  // 8. WebSocket interconnect connection
  socket = new JarvisWebSocket('ws://localhost:8000/ws');

  // 9. 3D Geointelligence Globe
  globe = new JarvisGlobe('globe-3d-canvas', 'globe-3d-container', (country) => {
    socket.send('command', { action: 'get_country_info', country: country.name });
    arcReactor.setThinking(true);
    neuralNetwork.startThinking();
  });

  // Connect clock
  startClock();

  // Connect signals to managers
  bindSocketEvents();
  bindInputEvents();
  initLaptopControls();
}


/**
 * Bind WebSocket telemetry triggers
 */
function bindSocketEvents() {
  const statusDot = document.getElementById('system-status-dot');
  const statusText = document.getElementById('system-status-text');
  const modelInfo = document.getElementById('header-model-info');

  // SOCKET ONLINE
  socket.on('socket_open', () => {
    statusDot.className = 'status-dot';
    statusText.innerText = 'ONLINE';
    statusText.style.color = 'var(--hud-green)';
    agentDashboard.addActivity("Transmitter gateway connected successfully.", "CORE");
  });

  // SOCKET OFFLINE / CLOSING
  socket.on('socket_close', () => {
    statusDot.className = 'status-dot disconnected';
    statusText.innerText = 'OFFLINE';
    statusText.style.color = 'var(--hud-red)';
    modelInfo.innerText = 'STANDBY';
    
    // Stop thinking animations on connection loss
    arcReactor.setThinking(false);
    neuralNetwork.stopThinking();
    chatManager.setTyping(false);

    agentDashboard.addActivity("Transmitter gateway closed. Accessing backup systems...", "CORE");
  });

  // SOCKET EXCEPTION
  socket.on('socket_error', () => {
    agentDashboard.addActivity("Security transmission interface warning.", "CORE");
  });

  // SERVER GREETING ON ESTABLISH
  socket.on('connected', (data) => {
    if (data.model) {
      modelInfo.innerText = data.model.toUpperCase();
    }
    
    const greeting = data.greeting || "JARVIS online, sir. Systems operational.";
    chatManager.addMessage(greeting, 'jarvis');
    
    // React audio wave on speech greeting
    audioViz.simulateSpeech(greeting);
    agentDashboard.addActivity(`Handshake established. Model initialized: ${data.model}`, "SYSTEM");
  });

  // REALTIME SERVER CHAT RESPONSE TOKEN STREAM
  socket.on('chat_response', (data) => {
    // If we're starting a new stream
    if (!activeStream && !data.done) {
      activeStream = chatManager.startStream();
      arcReactor.setThinking(true);
      neuralNetwork.startThinking();
      
      // Update header status indicators
      statusDot.className = 'status-dot thinking';
    }

    if (activeStream) {
      if (data.token) {
        activeStream.append(data.token);
      }

      if (data.done) {
        activeStream.end(data.full_text);
        activeStream = null;
        
        // Reset animations shortly after completion
        setTimeout(() => {
          if (!activeStream) {
            arcReactor.setThinking(false);
            neuralNetwork.stopThinking();
            statusDot.className = 'status-dot';
          }
        }, 1500);
      }
    }
  });

  // DYNAMIC SYSTEM METRICS UPDATER
  socket.on('system_stats', (data) => {
    systemMonitor.update(data);
    
    // Synchronize sliders and toggles dynamically from host metrics
    const volSlider = document.getElementById('slider-volume');
    const volVal = document.getElementById('volume-val');
    const brightSlider = document.getElementById('slider-brightness');
    const brightVal = document.getElementById('brightness-val');
    const wifiToggle = document.getElementById('toggle-wifi');
    
    if (data.volume !== undefined && document.activeElement !== volSlider) {
      const volPercent = Math.round(data.volume * 100);
      volSlider.value = volPercent;
      volVal.innerText = `${volPercent}%`;
    }
    
    if (data.brightness !== undefined && document.activeElement !== brightSlider) {
      brightSlider.value = data.brightness;
      brightVal.innerText = `${data.brightness}%`;
    }
    
    if (data.wifi_enabled !== undefined && document.activeElement !== wifiToggle) {
      wifiToggle.checked = data.wifi_enabled;
    }
    
    const chargingEl = document.getElementById('battery-charging-val');
    if (data.battery && chargingEl) {
      chargingEl.innerText = data.battery.charging ? "AC POWER CONNECTED" : "DC BATTERY POWER";
    }
  });


  // AGENT CARD & LOG UPDATES
  socket.on('agent_status', (data) => {
    if (data.agents) {
      agentDashboard.updateAgents(data.agents);
      
      // Log active subagent state changes
      data.agents.forEach(ag => {
        if (ag.status === 'working') {
          agentDashboard.addActivity(`Worker ${ag.name} activated for sub-routine operations.`, ag.name);
        }
      });
    }
    
    // Add real-time activity log entries from LeadAgent or workers
    if (data.log_entry) {
      agentDashboard.addActivity(data.log_entry.text, data.log_entry.agent);
    }
  });


  // THINKING STATE OVERLAY TOGGLE
  socket.on('thinking', (data) => {
    const active = !!data.active;
    arcReactor.setThinking(active);
    if (active) {
      neuralNetwork.startThinking();
      chatManager.setTyping(true);
      statusDot.className = 'status-dot thinking';
    } else {
      neuralNetwork.stopThinking();
      chatManager.setTyping(false);
      statusDot.className = 'status-dot';
    }
  });

  // REAL-TIME SENTENCE-LEVEL STREAMING TTS VOICE PIPELINE
  socket.on('tts_chunk', (data) => {
    if (data.audio_url && chatManager) {
      chatManager.enqueueAudio(data.audio_url, data.text);
    }
  });

  // VISUAL COGNITIVE REASONING PROTOCOLS LOADER
  socket.on('cognitive_log', (data) => {
    if (data.text) {
      console.log(`[Cognitive Brain] ${data.text}`);
      
      const cogConsole = document.getElementById('cognitive-console');
      if (cogConsole) {
        // Clear default placeholder on first real thought log
        if (cogConsole.innerText.includes("Awaiting command") || cogConsole.innerText.includes("Awaiting cognitive")) {
          cogConsole.innerHTML = "";
        }
        
        const entry = document.createElement('div');
        entry.className = 'cognitive-entry';
        const formattedTime = new Date().toTimeString().split(' ')[0];
        entry.innerHTML = `&gt; <span class="cog-time">[${formattedTime}]</span> ${data.text}`;
        cogConsole.appendChild(entry);
        cogConsole.scrollTop = cogConsole.scrollHeight;
      }
      
      if (agentDashboard) {
        agentDashboard.addActivity(data.text, "BRAIN");
      }
    }
  });


  // WORKSPACE OR TOOL INSTRUCTION LOGS
  socket.on('tool_result', (data) => {
    if (data.tool) {
      const toolName = data.tool;
      const desc = `Invoking tactical tool: ${toolName}`;
      agentDashboard.addActivity(desc, "ENGINEER");

      // Draw custom visual tool result block inside Chat bubbles list
      const timestamp = chatManager.formatTime(new Date());
      const chatContainer = document.getElementById('chat-messages');
      if (chatContainer) {
        const toolDiv = document.createElement('div');
        toolDiv.className = 'tool-result-card';
        
        let resultString = '';
        try {
          resultString = typeof data.result === 'object' 
            ? JSON.stringify(data.result, null, 2) 
            : String(data.result);
        } catch(e) {
          resultString = String(data.result);
        }

        toolDiv.innerHTML = `
          <div class="tool-header">
            <span>🔧 SYSTEM EXECUTION RESULT [${toolName.toUpperCase()}]</span>
            <span>${timestamp}</span>
          </div>
          <div class="tool-body">${resultString}</div>
        `;
        chatContainer.appendChild(toolDiv);
        chatManager.scrollToBottom(true);
      }
    }
  });

  // FAILURES / LOG METRICS SYSTEM WARNINGS
  socket.on('error', (data) => {
    const errMessage = data.message || "Transmission core anomaly reported.";
    chatManager.addMessage(`**CRITICAL ERROR:** ${errMessage}`, 'jarvis');
    agentDashboard.addActivity(`Error encountered: ${errMessage}`, "WARNING");
  });
}

/**
 * Handle user messages transmission
 */
function bindInputEvents() {
  chatManager.onMessageSent((text) => {
    // 1. Add User bubble to chat log immediately
    chatManager.addMessage(text, 'user');
    
    // 2. Transmit chat payload to Server over WebSocket
    socket.send('chat_message', { text });

    // 3. Ignite local systems while server compiles
    arcReactor.setThinking(true);
    neuralNetwork.startThinking();
    chatManager.setTyping(true);

    agentDashboard.addActivity(`Command transmitted: "${text}"`, "SIR");
  });

  // Hotkey: Ctrl+Enter inside the interface triggers sends
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      chatManager.triggerSend();
    }
  });
}

/**
 * Live ticking military HUD timestamp clock
 */
function startClock() {
  const clockEl = document.getElementById('hud-clock');
  
  function updateTime() {
    const now = new Date();
    // UTC/military style clock
    const timeString = now.toTimeString().split(' ')[0] + " GMT";
    if (clockEl) {
      clockEl.innerText = timeString;
    }
  }
  
  updateTime();
  setInterval(updateTime, 1000);
}

/**
 * Bind Laptop quick setting sliders and switch actions
 */
function initLaptopControls() {
  console.log("[Core] Binding system settings controls listeners...");
  
  const volSlider = document.getElementById('slider-volume');
  const volVal = document.getElementById('volume-val');
  const brightSlider = document.getElementById('slider-brightness');
  const brightVal = document.getElementById('brightness-val');
  const wifiToggle = document.getElementById('toggle-wifi');
  const muteToggle = document.getElementById('toggle-mute');

  // Master Volume control slider
  if (volSlider) {
    volSlider.addEventListener('input', (e) => {
      const level = e.target.value;
      if (volVal) volVal.innerText = `${level}%`;
      socket.send('command', { action: 'set_volume', level: parseFloat(level) / 100 });
      agentDashboard.addActivity(`Adjusting system volume: ${level}%`, "SIR");
    });
  }

  // Monitor Brightness control slider
  if (brightSlider) {
    brightSlider.addEventListener('input', (e) => {
      const level = e.target.value;
      if (brightVal) brightVal.innerText = `${level}%`;
      socket.send('command', { action: 'set_brightness', level: parseInt(level) });
      agentDashboard.addActivity(`Adjusting brightness WMI: ${level}%`, "SIR");
    });
  }

  // WiFi toggle
  if (wifiToggle) {
    wifiToggle.addEventListener('change', (e) => {
      const enable = e.target.checked;
      socket.send('command', { action: 'toggle_wifi', enable: enable });
      agentDashboard.addActivity(`WiFi adapter: ${enable ? 'ENABLED' : 'DISABLED'}`, "SIR");
    });
  }

  // Mute toggle (emulates media key volumemute)
  if (muteToggle) {
    muteToggle.addEventListener('change', () => {
      socket.send('command', { action: 'media_control', media_action: 'volumemute' });
      agentDashboard.addActivity("Mute master key toggled.", "SIR");
    });
  }

  // Media controls buttons
  const prevBtn = document.getElementById('media-prev');
  const playBtn = document.getElementById('media-play');
  const nextBtn = document.getElementById('media-next');

  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      socket.send('command', { action: 'media_control', media_action: 'prevtrack' });
      agentDashboard.addActivity("Trigger media key: PREV", "SIR");
    });
  }

  if (playBtn) {
    playBtn.addEventListener('click', (e) => {
      playBtn.classList.toggle('active');
      socket.send('command', { action: 'media_control', media_action: 'playpause' });
      agentDashboard.addActivity("Trigger media key: PLAY/PAUSE", "SIR");
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      socket.send('command', { action: 'media_control', media_action: 'nexttrack' });
      agentDashboard.addActivity("Trigger media key: NEXT", "SIR");
    });
  }
}

/**
 * Global selectMenu handler for Tactical Command Deck
 */
window.selectMenu = function(menuKey) {
  console.log(`[Command Deck] Active module selected: ${menuKey}`);
  
  // Collapse/Expand Globe panel dynamically to give Tactical System Console the absolute maximum vertical space!
  const globePanel = document.getElementById('globe-panel-container');
  if (menuKey === 'geoint') {
    if (globePanel) {
      globePanel.style.display = 'flex';
      setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
      }, 80);
    }
  } else {
    if (globePanel) {
      globePanel.style.display = 'none';
    }
  }

  // 1. Visually update active menu items in left column list
  const menuItems = document.querySelectorAll('.tactical-menu-list .menu-item');
  menuItems.forEach(item => {
    item.classList.remove('active');
    const onclickStr = item.getAttribute('onclick') || '';
    if (onclickStr.includes(menuKey)) {
      item.classList.add('active');
    }
  });

  // 2. Play visual indicator highlights on corresponding HUD panels
  const panels = document.querySelectorAll('.hud-panel');
  panels.forEach(p => p.classList.remove('panel-focused-glow'));

  let targetPanel = null;
  let logText = "";
  
  switch(menuKey) {
    case 'geoint':
      targetPanel = document.getElementById('globe-panel-container');
      logText = "GEOINTELLIGENCE NET ONLINE, SIR. SELECT GEO-NODE PINPOINT FOR DOSSIERS.";
      if (window.agentDashboard) {
        window.agentDashboard.addActivity(logText, "ORCHESTRATOR");
      }
      break;
      
    case 'sysinfo':
      targetPanel = document.querySelector('.right-top-panel');
      logText = "SYSTEM TELEMETRY CHANNEL ENGAGED. REFRESHING DIAGNOSTICS...";
      if (window.agentDashboard) {
        window.agentDashboard.addActivity(logText, "SYSTEM");
      }
      if (window.socket) {
        window.socket.send('command', { action: 'get_system_stats' });
      }
      break;
      
    case 'commands':
      targetPanel = document.getElementById('dossier-panel');
      logText = "TERMINAL INTEGRATION MODE ENGAGED. READY FOR SHELL SUB-ROUTINES.";
      if (window.agentDashboard) {
        window.agentDashboard.addActivity(logText, "CODE");
      }
      if (window.chatManager) {
        window.chatManager.addMessage("`TERMINAL CONTROLLER ACTIVE:` Core subshell integration online, Sir. Enter local shell commands or click Gauges to diagnostic.", "jarvis");
      }
      break;
      
    case 'agents':
      targetPanel = document.querySelector('.left-top-panel');
      logText = "ORCHESTRATOR MATRIX EXPANDED. SUBAGENT TELEMETRIES REFRESHED.";
      if (window.agentDashboard) {
        window.agentDashboard.addActivity(logText, "ORCHESTRATOR");
      }
      break;
      
    case 'settings':
      targetPanel = document.querySelector('.middle-bottom-panel');
      logText = "LAPTOP CORE MANAGER ENGAGED. READY FOR QUICK CONTROL OVERRIDES.";
      if (window.agentDashboard) {
        window.agentDashboard.addActivity(logText, "SYSTEM");
      }
      break;
      
    case 'audio':
      targetPanel = document.querySelector('.hud-waveform-panel');
      logText = "AUDIO FREQUENCY ANALYSIS INITIATED. COMMENCING SOUND Telemetries...";
      if (window.agentDashboard) {
        window.agentDashboard.addActivity(logText, "AUDIO");
      }
      if (window.audioViz) {
        window.audioViz.simulateSpeech("SOUND CHECK FREQUENCIES ENGAGING");
      }
      break;
  }

  if (targetPanel) {
    targetPanel.classList.add('panel-focused-glow');
    targetPanel.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    setTimeout(() => {
      targetPanel.classList.remove('panel-focused-glow');
    }, 2500);
  }
}

