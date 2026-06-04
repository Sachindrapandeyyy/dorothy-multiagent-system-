/* ============================================================
   Dorothy OS v2.0 — Chat Module
   Message rendering, markdown, streaming, input handling
   ============================================================ */

import { sendWS } from './app.js';

// ── DOM ─────────────────────────────────────────────────────
const messagesContainer = document.getElementById('chat-messages-hud') || document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('btn-send');
const micBtn = document.getElementById('btn-voice-toggle') || document.getElementById('btn-mic');
const thinkingEl = document.getElementById('thinking-indicator');

let isStreaming = false;
let lastDorothyBubble = null;

// ── Markdown Renderer (lightweight) ─────────────────────────
function renderMarkdown(text) {
  let html = escapeHtml(text);

  // Code blocks (```)
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre><code class="lang-${lang}">${code.trim()}</code></pre>`;
  });

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  // Italic
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Images
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" loading="lazy">');

  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" style="color:var(--color-accent-cyan)">$1</a>');

  // Unordered lists
  html = html.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');

  // Ordered lists
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

  // Paragraphs — split on double newlines
  html = html.split(/\n\n+/).map(block => {
    block = block.trim();
    if (!block) return '';
    if (block.startsWith('<pre>') || block.startsWith('<ul>') || block.startsWith('<ol>') || block.startsWith('<li>')) {
      return block;
    }
    return '<p>' + block.replace(/\n/g, '<br>') + '</p>';
  }).join('');

  return html;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ── Time Formatter ──────────────────────────────────────────
function formatTime(date) {
  const h = String(date.getHours()).padStart(2, '0');
  const m = String(date.getMinutes()).padStart(2, '0');
  return `${h}:${m}`;
}

// ── Create Message Element ──────────────────────────────────
function createMessageEl(sender, content, timestamp) {
  const isUser = sender === 'user';
  const msg = document.createElement('div');
  msg.className = `chat-msg ${isUser ? 'user' : 'dorothy'}`;

  const meta = document.createElement('div');
  meta.className = 'msg-meta';
  meta.innerHTML = `
    <span class="msg-sender">${isUser ? 'YOU' : 'Dorothy'}</span>
    <span class="msg-time">${formatTime(timestamp || new Date())}</span>
  `;

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';

  if (isUser) {
    bubble.innerHTML = `<p>${escapeHtml(content)}</p>`;
  } else {
    bubble.innerHTML = renderMarkdown(content);
  }

  msg.appendChild(meta);
  msg.appendChild(bubble);

  return { msg, bubble };
}

// ── Auto-scroll ─────────────────────────────────────────────
function scrollToBottom() {
  requestAnimationFrame(() => {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  });
}

// ── Public API ──────────────────────────────────────────────

export function addUserMessage(text) {
  const { msg } = createMessageEl('user', text);
  messagesContainer.appendChild(msg);
  scrollToBottom();
}

export function addDorothyMessage(text) {
  const { msg, bubble } = createMessageEl('dorothy', text);
  messagesContainer.appendChild(msg);
  lastDorothyBubble = bubble;
  isStreaming = false;
  scrollToBottom();
}

export function startStream() {
  const { msg, bubble } = createMessageEl('dorothy', '');
  messagesContainer.appendChild(msg);
  lastDorothyBubble = bubble;
  lastDorothyBubble._rawText = '';
  isStreaming = true;
  scrollToBottom();
}

export function appendToken(token) {
  if (!lastDorothyBubble || !isStreaming) {
    startStream();
  }

  lastDorothyBubble._rawText = (lastDorothyBubble._rawText || '') + token;
  lastDorothyBubble.innerHTML = renderMarkdown(lastDorothyBubble._rawText);
  scrollToBottom();
}

export function finishStream() {
  isStreaming = false;
  lastDorothyBubble = null;
}

export function showThinking() {
  if (thinkingEl) {
    thinkingEl.classList.add('visible');
    scrollToBottom();
  }
}

export function hideThinking() {
  if (thinkingEl) {
    thinkingEl.classList.remove('visible');
  }
}

// ── Input Handling ──────────────────────────────────────────
function handleSend() {
  const text = chatInput.value.trim();
  if (!text) return;

  addUserMessage(text);
  chatInput.value = '';
  chatInput.style.height = 'auto';

  // Send via WebSocket in the format the backend expects
  sendWS({ type: 'chat_message', data: { message: text } });

  // Show thinking while waiting for response
  showThinking();
}

// Send button
sendBtn?.addEventListener('click', handleSend);

// Enter to send (Shift+Enter for new line)
chatInput?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSend();
  }
});

// Auto-resize textarea
chatInput?.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
});

let recognition = null;
let isRecording = false;

function initSpeechRecognition() {
  if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      console.log('[Dorothy] Speech interface online.');
      micBtn.classList.add('recording');
      micBtn.setAttribute('data-tooltip', 'Stop Listening');
    };

    recognition.onerror = (event) => {
      console.error('[Dorothy] Speech interface error:', event.error);
    };

    recognition.onend = () => {
      console.log('[Dorothy] Speech interface offline.');
      micBtn.classList.remove('recording');
      micBtn.setAttribute('data-tooltip', 'Voice Input');
      isRecording = false;
    };

    recognition.onresult = (event) => {
      let interimTranscript = '';
      let finalTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        } else {
          interimTranscript += transcript;
        }
      }

      if (finalTranscript.trim()) {
        const command = finalTranscript.trim();
        console.log('[Dorothy] Decoded command:', command);
        
        // Dynamic Wake Phrase filter (Hey Dorothy / Dorothy)
        const lowerCmd = command.toLowerCase();
        if (lowerCmd.includes('dorothy')) {
          const parts = lowerCmd.split('dorothy');
          const cleanCommand = parts[parts.length - 1].trim();
          
          if (cleanCommand) {
            addUserMessage(cleanCommand);
            sendWS({ type: 'chat_message', data: { message: cleanCommand } });
            showThinking();
          } else {
            // Wake phrase only
            chatInput.value = 'Yes, Commander?';
          }
        } else {
          // Direct speech command execution
          addUserMessage(command);
          sendWS({ type: 'chat_message', data: { message: command } });
          showThinking();
        }
        chatInput.value = '';
      } else if (interimTranscript) {
        chatInput.value = interimTranscript;
      }
    };
  } else {
    console.warn('[Dorothy] Web Speech Recognition is unsupported in this container.');
  }
}

// Mic button handler
micBtn?.addEventListener('click', () => {
  if (!recognition) {
    initSpeechRecognition();
  }

  if (!recognition) {
    console.error('Speech recognition not available.');
    return;
  }

  if (isRecording) {
    recognition.stop();
  } else {
    isRecording = true;
    recognition.start();
  }
});

// ── Sequential Audio Playback Queue ─────────────────────────
const audioQueue = [];
let isPlayingAudio = false;

function playNextAudio() {
  if (audioQueue.length === 0) {
    isPlayingAudio = false;
    return;
  }

  isPlayingAudio = true;
  const url = audioQueue.shift();
  const audio = new Audio(url);
  
  audio.addEventListener('ended', () => {
    playNextAudio();
  });
  
  audio.addEventListener('error', (e) => {
    console.warn('[Dorothy] Audio playback error:', e);
    playNextAudio();
  });

  audio.play().catch(e => {
    console.warn('[Dorothy] Autoplay blocked or failed:', e);
    playNextAudio();
  });
}

function queueAudio(url) {
  audioQueue.push(url);
  if (!isPlayingAudio) {
    playNextAudio();
  }
}

// ── Listen for WebSocket messages ───────────────────────────
window.addEventListener('dorothy:ws', (e) => {
  const data = e.detail;
  console.log('[Chat WS Event]', data);

  // Backend sends chat_response wrapper: {type: "chat_response", data: {type: "token", content: "..."}}
  if (data.type === 'chat_response') {
    const inner = data.data || {};

    if (inner.type === 'token') {
      hideThinking();
      appendToken(inner.content || '');
    } else if (inner.type === 'thinking') {
      if (inner.data?.active) {
        showThinking();
      } else {
        hideThinking();
      }
    } else if (inner.type === 'end') {
      hideThinking();
      finishStream();
    } else if (inner.type === 'error') {
      hideThinking();
      finishStream();
      addDorothyMessage(`⚠️ Error: ${inner.message || 'Unknown error'}`);
    } else if (inner.type === 'tool_result') {
      const toolData = inner.data || {};
      console.log(`[TOOL] ${toolData.tool}:`, toolData.result);

      // Widescreen HUD: Update Sandbox Terminal console
      if (toolData.tool === 'execute_python_sandbox') {
        const feedEl = document.getElementById('sandbox-console-feed');
        if (feedEl) {
          const res = toolData.result || {};
          let linesHTML = `<div class="sandbox-line" style="color: var(--color-accent-teal); border-top: 1px dashed rgba(0, 194, 255, 0.15); padding-top: 4px; margin-top: 4px; font-weight: bold;">sandbox: execution complete (status=${res.success ? '0' : '1'})</div>`;
          if (res.stdout) {
            linesHTML += `<div class="sandbox-line" style="color:#ffffff;">&nbsp;&nbsp;${escapeHtml(res.stdout).replace(/\n/g, '<br>&nbsp;&nbsp;')}</div>`;
          }
          if (res.stderr) {
            linesHTML += `<div class="sandbox-line" style="color:#ff3b3b; font-weight: bold;">&nbsp;&nbsp;${escapeHtml(res.stderr).replace(/\n/g, '<br>&nbsp;&nbsp;')}</div>`;
          }
          if (res.self_reflection_needed && res.error_suggestion) {
            linesHTML += `<div class="sandbox-line" style="color: #ffb800; font-style: italic;">&nbsp;&nbsp;[REFLECTION] suggestion: ${escapeHtml(res.error_suggestion)}</div>`;
          }
          
          const wrapper = document.createElement('div');
          wrapper.innerHTML = linesHTML;
          feedEl.appendChild(wrapper);
          feedEl.scrollTop = feedEl.scrollHeight;
        }
      }


      // Widescreen HUD: Update screen perception snapshot view
      if (toolData.tool === 'capture_desktop_screenshot' || toolData.tool === 'locate_and_click_ui_element') {
        const snap = document.getElementById('hud-perception-snapshot');
        if (snap) {
          const filename = toolData.result?.filename || 'vlm_perception.png';
          snap.src = `/captures/${filename}`;
          snap.style.display = 'block';
        }
      }
    }
  }

  // TTS audio chunks
  if (data.type === 'tts_chunk') {
    const filename = data.data?.filename;
    if (filename) {
      queueAudio(`/audio/${filename}`);
    }
  }

  // Widescreen HUD: Manual Biometrics result handler
  if (data.type === 'biometric_status') {
    const status = data.data?.status || 'REFUSED';
    const descEl = document.getElementById('bio-status-desc');
    const labelEl = document.getElementById('bio-status-label');
    const iconEl = document.getElementById('bio-icon');
    
    if (descEl && labelEl && iconEl) {
      if (status === 'GRANTED') {
        labelEl.textContent = 'GRANTED';
        labelEl.style.color = '#00ff88';
        descEl.textContent = 'BIOMETRICS: APPROVED';
        descEl.style.color = '#00ff88';
        iconEl.className = 'bio-icon-glow granted';
        iconEl.textContent = '🔓';
      } else {
        labelEl.textContent = 'REFUSED';
        labelEl.style.color = '#ff3b3b';
        descEl.textContent = 'BIOMETRICS: REFUSED';
        descEl.style.color = '#ff3b3b';
        iconEl.className = 'bio-icon-glow refused';
        iconEl.textContent = '🔒';
      }
      
      // Auto-restore after 3 seconds
      setTimeout(() => {
        labelEl.textContent = 'ACTIVE';
        labelEl.style.color = '';
        descEl.textContent = 'WIN_HELLO: GRANTED';
        descEl.style.color = '#00ff88';
        iconEl.className = 'bio-icon-glow';
        iconEl.textContent = '🔒';
      }, 4000);
    }
  }
});

// ── Sandbox Console Command Inputs ────────────────────────
const sandboxInput = document.getElementById('sandbox-term-input');
sandboxInput?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    const code = sandboxInput.value.trim();
    if (!code) return;

    sandboxInput.value = '';

    const feedEl = document.getElementById('sandbox-console-feed');
    if (feedEl) {
      const cmdLine = document.createElement('div');
      cmdLine.className = 'sandbox-line';
      cmdLine.innerHTML = `<span style="color: var(--color-accent-cyan); font-weight: bold;">&gt;</span> <span style="color: #ffffff;">${escapeHtml(code)}</span>`;
      feedEl.appendChild(cmdLine);
      
      const runningLine = document.createElement('div');
      runningLine.className = 'sandbox-line';
      runningLine.style.color = 'var(--text-muted)';
      runningLine.textContent = 'running sandbox compiler...';
      feedEl.appendChild(runningLine);
      
      feedEl.scrollTop = feedEl.scrollHeight;
    }

    sendWS({ type: 'command', data: { action: 'execute_sandbox', code: code } });
  }
});

// ── Biometric Shield Click Trigger ─────────────────────────
document.getElementById('bio-shield-trigger')?.addEventListener('click', () => {
  const labelEl = document.getElementById('bio-status-label');
  const descEl = document.getElementById('bio-status-desc');
  if (labelEl && descEl) {
    labelEl.textContent = 'PENDING';
    labelEl.style.color = 'var(--color-accent-amber)';
    descEl.textContent = 'WIN_HELLO: CHALLENGING';
    descEl.style.color = 'var(--color-accent-amber)';
  }
  console.log('[BIOMETRICS] Directing manual credentials verification...');
  sendWS({ type: 'command', data: { action: 'trigger_biometrics' } });
});

// ── Welcome message on load ─────────────────────────────────
setTimeout(() => {
  addDorothyMessage(
    `Welcome back, Commander. Dorothy OS **v2.0** is online.\n\nAll systems nominal. I'm ready to assist with any task — from system control to research to multi-agent orchestration.\n\nHow can I help you today?`
  );
}, 500);

