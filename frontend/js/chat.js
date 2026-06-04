/**
 * ChatManager Class
 * Controls chat bubble logs, message history, regex markdown parsed rendering, 
 * streaming response appends, typing animation indicators, and scroll offsets.
 */
class ChatManager {
  constructor(containerId, inputId, sendBtnId, micBtnId, typingId) {
    this.container = document.getElementById(containerId);
    this.input = document.getElementById(inputId);
    this.sendBtn = document.getElementById(sendBtnId);
    this.micBtn = document.getElementById(micBtnId);
    this.typingIndicator = document.getElementById(typingId);
    
    this.onMessageSentCallbacks = [];
    this.isMicActive = false;
    this.userHasScrolledUp = false;

    // Bind event hooks
    this.initEvents();
    this.initDirectSpeech();
    this.audioQueue = [];
    this.audioPlayer = null;
  }

  /**
   * Register callbacks for when the user transmits a message
   */
  onMessageSent(callback) {
    this.onMessageSentCallbacks.push(callback);
  }

  /**
   * Listen to scroll movements and key inputs
   */
  initEvents() {
    // Input Key Press
    if (this.input) {
      this.input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.triggerSend();
        }
      });
    }

    // Send Button Trigger
    if (this.sendBtn) {
      this.sendBtn.addEventListener('click', () => this.triggerSend());
    }

    // Mic Voice Toggle (Visual mock & Speech Recognition if available)
    if (this.micBtn) {
      this.micBtn.addEventListener('click', () => this.toggleMic());
    }

    // Track scroll events to avoid forcing scroll down if user is reading logs
    if (this.container) {
      this.container.addEventListener('scroll', () => {
        const threshold = 50; // pixels from bottom
        const currentScroll = this.container.scrollTop + this.container.clientHeight;
        const totalHeight = this.container.scrollHeight;
        
        // If user is more than 'threshold' pixels away from bottom, mark they scrolled up
        this.userHasScrolledUp = (totalHeight - currentScroll) > threshold;
      });
    }
  }

  /**
   * Initialize continuous hands-free voice interface
   */
  initDirectSpeech() {
    this.isDirectSpeechActive = false;
    this.isWakeWordEnabled = false;
    this.isTTSSpeaking = false;
    this.directSpeechRecognition = null;

    this.chkDirectSpeech = document.getElementById('chk-direct-speech');
    this.chkWakeWord = document.getElementById('chk-wake-word');

    if (this.chkDirectSpeech) {
      this.chkDirectSpeech.addEventListener('change', (e) => {
        this.isDirectSpeechActive = e.target.checked;
        if (this.isDirectSpeechActive) {
          // Deactivate normal toggle mic mode to prevent resource locks
          if (this.isMicActive) {
            this.toggleMic();
          }
          this.startDirectSpeech();
        } else {
          this.stopDirectSpeech();
        }
      });
    }

    if (this.chkWakeWord) {
      this.chkWakeWord.addEventListener('change', (e) => {
        this.isWakeWordEnabled = e.target.checked;
        console.log(`[Voice] Wake Word detection status: ${this.isWakeWordEnabled ? "ENGAGED" : "DISENGAGED"}`);
      });
    }
  }

  /**
   * Start or resume continuous speech capture session
   */
  startDirectSpeech() {
    if (!this.isDirectSpeechActive) return;
    if (this.isTTSSpeaking) {
      console.log("[Voice] Reserving Speech Recognition: TTS is actively playing.");
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.error("[Voice] Speech Recognition API not supported in this client browser.");
      if (this.chkDirectSpeech) this.chkDirectSpeech.checked = false;
      this.isDirectSpeechActive = false;
      this.addMessage("Speech Recognition API is not supported in your browser, Sir.", "jarvis");
      return;
    }

    if (this.directSpeechRecognition) {
      try {
        this.directSpeechRecognition.stop();
      } catch(e) {}
    }

    console.log("[Voice] Engaging Continuous Direct Speech Capture...");
    this.directSpeechRecognition = new SpeechRecognition();
    this.directSpeechRecognition.continuous = false;
    this.directSpeechRecognition.interimResults = true;
    this.directSpeechRecognition.lang = 'en-IN';

    // Apply active pulsing mic class
    this.micBtn.classList.add('direct-speech-listening');
    this.input.placeholder = this.isWakeWordEnabled 
      ? "JARVIS CORE ONLINE... WAKE COMMAND REQUIRED ('JARVIS...')"
      : "JARVIS LISTENING... DIRECT VOICE TRANSMIT ACTIVE.";

    this.directSpeechRecognition.onresult = (event) => {
      let interimTranscript = '';
      let finalTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        } else {
          interimTranscript += event.results[i][0].transcript;
        }
      }

      if (interimTranscript) {
        this.input.value = interimTranscript;
      }

      if (finalTranscript) {
        finalTranscript = finalTranscript.trim();
        this.input.value = finalTranscript;
        console.log(`[Voice] Raw final transcript: "${finalTranscript}"`);

        if (this.isWakeWordEnabled) {
          const cleanText = finalTranscript.toLowerCase();
          if (cleanText.includes("jarvis") || cleanText.includes("jarves") || cleanText.includes("jaavis") || cleanText.includes("जाविर्स") || cleanText.includes("जार्विस")) {
            let processedText = finalTranscript
              .replace(/jarvis/gi, '')
              .replace(/jarves/gi, '')
              .replace(/jaavis/gi, '')
              .replace(/जाविर्स/g, '')
              .replace(/जार्विस/g, '')
              .trim();
              
            processedText = processedText.replace(/^[,.\s]+/, '');
            
            if (processedText) {
              console.log(`[Voice] Wake word detected. Synthesizing request: "${processedText}"`);
              this.input.value = processedText;
              this.triggerSend();
            } else {
              this.input.value = "";
              this.input.placeholder = "YES SIR? STATE YOUR COMMAND...";
            }
          } else {
            console.log("[Voice] Wake word 'Jarvis' not detected. Discarding.");
            this.input.value = "";
          }
        } else {
          this.triggerSend();
        }
      }
    };

    this.directSpeechRecognition.onerror = (err) => {
      if (err.error === 'no-speech') {
        return;
      }
      console.warn('[Voice] Speech recognition session warning:', err.error);
      if (err.error === 'not-allowed') {
        console.error('[Voice] Microphone access blocked.');
        this.addMessage("Microphone capture access denied, Sir. Please check browser settings.", "jarvis");
        if (this.chkDirectSpeech) this.chkDirectSpeech.checked = false;
        this.isDirectSpeechActive = false;
        this.stopDirectSpeech();
      }
    };

    this.directSpeechRecognition.onend = () => {
      if (this.isDirectSpeechActive && !this.isTTSSpeaking) {
        setTimeout(() => {
          this.startDirectSpeech();
        }, 100);
      } else {
        this.micBtn.classList.remove('direct-speech-listening');
        if (!this.isTTSSpeaking) {
          this.input.placeholder = "ACCESS INTERCONNECT PORTAL OR SEND DIRECT COMMAND...";
        }
      }
    };

    try {
      this.directSpeechRecognition.start();
    } catch(e) {
      console.warn("[Voice] Failed to start speech recognition (likely active):", e);
    }
  }

  /**
   * Stop continuous speech capture session
   */
  stopDirectSpeech() {
    this.isDirectSpeechActive = false;
    this.micBtn.classList.remove('direct-speech-listening');
    this.input.placeholder = "ACCESS INTERCONNECT PORTAL OR SEND DIRECT COMMAND...";
    if (this.directSpeechRecognition) {
      try {
        this.directSpeechRecognition.stop();
      } catch(e) {}
      this.directSpeechRecognition = null;
    }
  }

  /**
   * Synchronize audio synthesizer speech status
   * Prevents system self-loop feedback loops
   */
  setTTSSpeaking(active) {
    this.isTTSSpeaking = !!active;
    console.log(`[Voice] Speaking TTS state update: ${this.isTTSSpeaking}`);

    if (this.isTTSSpeaking) {
      if (this.directSpeechRecognition) {
        try {
          this.directSpeechRecognition.stop();
        } catch(e) {}
      }
      this.micBtn.classList.remove('direct-speech-listening');
      this.input.placeholder = "JARVIS TRANSMITTING AUDIBLE VOICE TELEMETRY...";
    } else {
      if (this.isDirectSpeechActive) {
        setTimeout(() => {
          this.startDirectSpeech();
        }, 300);
      } else {
        this.input.placeholder = "ACCESS INTERCONNECT PORTAL OR SEND DIRECT COMMAND...";
      }
    }
  }

  /**
   * Enqueue a new streaming TTS sentence chunk and coordinate seamless playback
   */
  enqueueAudio(url, text) {
    if (!url) return;
    console.log(`[Voice Queue] Enqueuing chunk: "${text ? text.substring(0, 20) : '...'}"`);
    this.audioQueue.push({ url, text });
    
    // If not currently playing, start playing immediately
    if (!this.isTTSSpeaking) {
      this.setTTSSpeaking(true);
      this.playNextAudio();
    }
  }

  /**
   * Play the next synthesized sentence chunk in the queue
   */
  playNextAudio() {
    if (this.audioQueue.length === 0) {
      console.log("[Voice Queue] Playback completed. All chunks vocalized.");
      this.setTTSSpeaking(false);
      this.audioPlayer = null;
      return;
    }

    const chunk = this.audioQueue.shift();
    console.log(`[Voice Queue] Vocalizing segment: "${chunk.text ? chunk.text.substring(0, 30) : ''}..."`);

    // Focus footer waveform reaction
    if (window.audioViz) {
      window.audioViz.simulateSpeech(chunk.text || "Vocalizing segment telemetry");
    }
    if (window.agentDashboard) {
      window.agentDashboard.addActivity(`Vocalizing synthesized dialogue: "${chunk.text ? chunk.text.substring(0, 20) : ''}..."`, "AUDIO");
    }

    this.audioPlayer = new Audio(chunk.url);
    
    this.audioPlayer.onended = () => {
      this.playNextAudio();
    };

    this.audioPlayer.onerror = (err) => {
      console.warn("[Voice Queue] Playback failed for chunk:", chunk.url, err);
      this.playNextAudio(); // continue to next chunk despite error
    };

    this.audioPlayer.play().catch(err => {
      console.warn("[Voice Queue] Playback blocked by browser autoplay policies:", err);
      this.playNextAudio(); // continue/skip
    });
  }

  /**
   * Process and emit input values
   */
  triggerSend() {
    if (!this.input) return;
    const text = this.input.value.trim();
    if (!text) return;

    // Direct terminal command syntax shortcut: e.g. "> ipconfig" or "$ dir"
    if (text.startsWith('$') || text.startsWith('>')) {
      const cmdStr = text.substring(1).trim();
      if (cmdStr) {
        // Add User message block representing shell command
        this.addMessage(`<code>&gt; ${cmdStr}</code>`, 'user');
        if (window.socket) {
          window.socket.send('command', { action: 'execute_terminal', command: cmdStr });
          if (window.agentDashboard) {
            window.agentDashboard.addActivity(`Direct shell instruction dispatched: "${cmdStr}"`, "SIR");
          }
        }
        this.input.value = '';
        return;
      }
    }

    // Emit event to subscribers (app orchestrator)
    this.onMessageSentCallbacks.forEach(cb => cb(text));
    
    // Clear field
    this.input.value = '';
  }

  /**
   * Toggle Voice Dictation input state
   */
  toggleMic() {
    this.isMicActive = !this.isMicActive;
    
    if (this.isMicActive) {
      this.micBtn.classList.add('active');
      this.input.placeholder = "LISTENING SIR... SPEAK DIRECTLY INTO CAPTURE ARRAY.";
      
      // Attempt to access web kit speech recognition if available
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SpeechRecognition) {
        this.recognition = new SpeechRecognition();
        this.recognition.continuous = false;
        this.recognition.interimResults = false;
        this.recognition.lang = 'en-IN';

        this.recognition.onresult = (event) => {
          const transcript = event.results[0][0].transcript;
          this.input.value = transcript;
          this.toggleMic(); // Auto deactivate mic on speech finish
          this.triggerSend();
        };

        this.recognition.onerror = (err) => {
          console.error('[Chat] Speech Recognition error:', err);
          this.toggleMic();
        };

        this.recognition.start();
      } else {
        console.warn('[Chat] Speech Recognition API not supported in this browser.');
        // Simulation fallback for visuals
        setTimeout(() => {
          if (this.isMicActive) {
            this.input.value = "Show system stats";
            this.toggleMic();
            this.triggerSend();
          }
        }, 3000);
      }
    } else {
      this.micBtn.classList.remove('active');
      this.input.placeholder = "ACCESS INTERCONNECT PORTAL OR SEND DIRECT COMMAND...";
      if (this.recognition) {
        try {
          this.recognition.stop();
        } catch(e) {}
      }
    }
  }

  /**
   * Toggle visual typing dots
   * @param {boolean} visible - Display state
   */
  setTyping(visible) {
    if (!this.typingIndicator) return;
    this.typingIndicator.style.display = visible ? 'flex' : 'none';
    this.scrollToBottom();
  }

  /**
   * Helper to format double digits
   */
  formatTime(date) {
    return date.toTimeString().split(' ')[0];
  }

  /**
   * Basic markdown parse conversion for scifi clean layouts
   */
  parseMarkdown(text) {
    // Escape standard HTML
    let html = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // 1. Code Blocks: ```code``` -> <pre><code>code</code></pre>
    html = html.replace(/```([\s\S]*?)```/g, (match, code) => {
      return `<pre><code>${code.trim()}</code></pre>`;
    });

    // 2. Inline Code: `code` -> <code>code</code>
    html = html.replace(/`([^`\n]+)`/g, '<code>$1</code>');

    // 3. Bold Styling: **text** -> <strong>text</strong>
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // 4. Bullet lists: * item or - item -> <li>item</li>
    html = html.replace(/^\s*[-*]\s+(.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>');

    // 5. Linebreaks: \n -> <br> (only if not inside <pre>)
    // Splitting code blocks to avoid messing them up with <br>
    const parts = html.split(/(<pre>[\s\S]*?<\/pre>)/);
    for (let i = 0; i < parts.length; i++) {
      if (!parts[i].startsWith('<pre>')) {
        parts[i] = parts[i].replace(/\n/g, '<br>');
      }
    }
    html = parts.join('');
    
    // 6. Markdown Images: ![caption](url) -> custom visual container
    html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, caption, url) => {
      return `<div class="hud-dossier-image" style="margin-top: 10px; margin-bottom: 10px;"><img src="${url}" alt="${caption}" style="max-width: 100%; border: 1px solid var(--hud-cyan); box-shadow: 0 0 10px rgba(0,255,255,0.25); display: block;"><span class="img-caption" style="display: block; font-size: 0.7rem; color: var(--hud-text-dim); margin-top: 5px; font-family: 'Share Tech Mono', monospace;">📡 OPTICAL FEED // ${caption.toUpperCase()}</span></div>`;
    });

    return html;
  }

  /**
   * Add a static full bubble directly to the chat
   * @param {string} text - Message body
   * @param {string} sender - 'jarvis' or 'user'
   */
  addMessage(text, sender = 'jarvis', timestamp = null) {
    if (!this.container) return;

    const senderName = sender === 'user' ? 'SIR' : 'J.A.R.V.I.S.';
    const formattedTime = timestamp ? timestamp : this.formatTime(new Date());
    const parsedHTML = this.parseMarkdown(text);

    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-msg chat-msg-${sender}`;

    messageDiv.innerHTML = `
      <div class="chat-msg-meta">
        <span class="chat-msg-sender">${senderName}</span>
        <span class="chat-msg-time">${formattedTime}</span>
      </div>
      <div class="chat-msg-bubble">
        ${parsedHTML}
      </div>
    `;

    this.container.appendChild(messageDiv);
    this.scrollToBottom(true);
  }

  /**
   * Setup stream element for chunks loading
   */
  startStream() {
    if (!this.container) return null;
    this.setTyping(false); // Disable typing dots on stream start

    const formattedTime = this.formatTime(new Date());
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'chat-msg chat-msg-jarvis';
    messageDiv.innerHTML = `
      <div class="chat-msg-meta">
        <span class="chat-msg-sender">J.A.R.V.I.S.</span>
        <span class="chat-msg-time">${formattedTime}</span>
      </div>
      <div class="chat-msg-bubble"></div>
    `;

    this.container.appendChild(messageDiv);
    const bubble = messageDiv.querySelector('.chat-msg-bubble');
    
    let rawText = '';
    const chatManagerInstance = this;

    // Return reference controller object
    return {
      append: (token) => {
        rawText += token;
        bubble.innerHTML = chatManagerInstance.parseMarkdown(rawText);
        chatManagerInstance.scrollToBottom();
      },
      end: (fullText = '') => {
        if (fullText) {
          rawText = fullText;
        }
        bubble.innerHTML = chatManagerInstance.parseMarkdown(rawText);
        chatManagerInstance.scrollToBottom(true);
      }
    };
  }

  /**
   * Scroll panel down
   * @param {boolean} force - Skip scrolled-up inspection check
   */
  scrollToBottom(force = false) {
    if (!this.container) return;
    if (force || !this.userHasScrolledUp) {
      this.container.scrollTop = this.container.scrollHeight;
    }
  }
}
