/* ============================================================
   Dorothy OS v2.0 — Voice Pipeline Module
   WebRTC mic capture → WAV encoding → WebSocket → STT → TTS
   Features:
   - Push-to-talk (hold mic button)
   - Continuous mode (toggle mic, VAD auto-sends)
   - Real-time waveform visualization
   - Seamless TTS audio queue (streaming, no gaps)
   - Voice status HUD overlay
   ============================================================ */

// ── Configuration ────────────────────────────────────────────
const VOICE_WS_URL = `ws://${location.host}/ws/voice`;
const SAMPLE_RATE = 16000;     // faster-whisper expects 16kHz
const VAD_SILENCE_MS = 900;    // ms of silence before auto-send
const VAD_ENERGY_THRESH = 0.008; // amplitude threshold for voice activity
const MAX_RECORDING_S = 30;    // safety max record time

// ── State ────────────────────────────────────────────────────
let voiceWS = null;
let wsConnected = false;
let wsReconnectDelay = 2000;   // starts at 2s, backs off to 15s max
let wsReconnectTimer = null;
let audioCtx = null;
let mediaStream = null;
let scriptProcessor = null;
let sourceNode = null;
let analyserNode = null;

let isRecording = false;
let isContinuousMode = false;
let audioBuffer = [];          // Float32 PCM chunks while recording
let vadSilenceTimer = null;
let recordingStartTime = 0;
let maxRecordTimer = null;
let animFrame = null;

// ── Audio Queue (Streaming TTS Playback) ─────────────────────
const ttsQueue = [];
let ttsPlaying = false;
let ttsCurrentAudio = null;

// ── DOM Elements ─────────────────────────────────────────────
let micBtn, voiceOrb, voiceStatusLabel, voiceWaveCanvas, waveCtx;
let voiceOverlay, voiceTranscriptEl, voiceModeToggle;
let chatInput;

// ============================================================
// INITIALIZATION
// ============================================================

function initVoiceUI() {
  micBtn           = document.getElementById('voice-orb');        // The orb IS the mic button
  voiceOrb         = document.getElementById('voice-orb');
  voiceStatusLabel = document.getElementById('voice-orb-status');
  voiceWaveCanvas  = document.getElementById('voice-wave-canvas');
  voiceOverlay     = document.getElementById('voice-hud-overlay');
  voiceTranscriptEl= document.getElementById('voice-transcript-live');
  voiceModeToggle  = document.getElementById('btn-voice-mode-toggle');
  chatInput        = document.getElementById('chat-input');

  if (voiceWaveCanvas) {
    waveCtx = voiceWaveCanvas.getContext('2d');
  }

  // Wire buttons
  micBtn?.addEventListener('mousedown',  onMicPressStart);
  micBtn?.addEventListener('mouseup',    onMicPressEnd);
  micBtn?.addEventListener('touchstart', onMicPressStart, { passive: true });
  micBtn?.addEventListener('touchend',   onMicPressEnd,   { passive: true });

  voiceModeToggle?.addEventListener('click', toggleContinuousMode);

  // Connect voice WebSocket
  connectVoiceWS();

  setVoiceStatus('idle', '🎙️ Hold to speak');
  console.log('[Dorothy Voice] Pipeline initialized.');
}

// ============================================================
// WEBSOCKET
// ============================================================

function connectVoiceWS() {
  if (voiceWS && (voiceWS.readyState === WebSocket.OPEN || voiceWS.readyState === WebSocket.CONNECTING)) return;
  if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }

  setBadge('CONNECTING', '#ffb800');
  voiceWS = new WebSocket(VOICE_WS_URL);
  voiceWS.binaryType = 'arraybuffer';

  voiceWS.onopen = () => {
    wsConnected = true;
    wsReconnectDelay = 2000;   // reset backoff on success
    setVoiceStatus('ready', '✅ Voice ready');
    setBadge('LIVE', '#00ff88');
    console.log('[Dorothy Voice] WebSocket connected.');
  };

  voiceWS.onclose = () => {
    wsConnected = false;
    setVoiceStatus('offline', '⚠️ Reconnecting...');
    setBadge('OFFLINE', '#ff4444');
    console.warn(`[Dorothy Voice] WS disconnected. Retrying in ${wsReconnectDelay / 1000}s...`);
    wsReconnectTimer = setTimeout(() => {
      voiceWS = null;
      connectVoiceWS();
    }, wsReconnectDelay);
    wsReconnectDelay = Math.min(wsReconnectDelay * 1.5, 15000); // backoff up to 15s
  };

  voiceWS.onerror = (e) => {
    console.error('[Dorothy Voice] WebSocket error:', e);
  };

  voiceWS.onmessage = (event) => {
    handleVoiceWSMessage(event.data);
  };
}

function sendVoiceWSText(obj) {
  if (voiceWS && voiceWS.readyState === WebSocket.OPEN) {
    voiceWS.send(JSON.stringify(obj));
  }
}

function sendVoiceWSBinary(buffer) {
  if (voiceWS && voiceWS.readyState === WebSocket.OPEN) {
    voiceWS.send(buffer);
  }
}

// ============================================================
// WEBSOCKET MESSAGE HANDLER
// ============================================================

function handleVoiceWSMessage(rawData) {
  let data;
  try {
    data = JSON.parse(rawData);
  } catch {
    return;
  }

  const type = data.type;

  // Voice-specific events
  if (type === 'voice_status') {
    const { status, label } = data.data || {};
    setVoiceStatus(status, label);
  }

  if (type === 'voice_transcript') {
    const text = data.data?.text || '';
    showLiveTranscript(text);
    // Mirror to chat input for text visibility
    if (chatInput) chatInput.value = text;
  }

  // Streaming TTS audio
  if (type === 'tts_chunk') {
    const filename = data.data?.filename;
    if (filename) {
      enqueueTTS(`/audio/${filename}`);
    }
  }

  // Streaming response tokens — dispatch to chat module
  if (type === 'chat_response') {
    window.dispatchEvent(new CustomEvent('dorothy:ws', { detail: data }));
  }

  // Cognitive logs
  if (type === 'cognitive_log') {
    window.dispatchEvent(new CustomEvent('dorothy:ws', { detail: data }));
  }

  // Pass all events to the main app event bus too
  window.dispatchEvent(new CustomEvent('dorothy:ws', { detail: data }));
}

// ============================================================
// MIC CAPTURE
// ============================================================

async function initAudioContext() {
  if (audioCtx && audioCtx.state !== 'closed') return true;
  try {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SAMPLE_RATE });
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: SAMPLE_RATE,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      }
    });
    console.log('[Dorothy Voice] Microphone access granted.');
    return true;
  } catch (err) {
    console.error('[Dorothy Voice] Mic access denied:', err);
    setVoiceStatus('error', '🚫 Mic access denied');
    return false;
  }
}

async function startRecording() {
  if (isRecording) return;
  if (!await initAudioContext()) return;

  // Resume suspended AudioContext (browser policy)
  if (audioCtx.state === 'suspended') await audioCtx.resume();

  audioBuffer = [];
  isRecording = true;
  recordingStartTime = Date.now();

  // Create nodes
  sourceNode   = audioCtx.createMediaStreamSource(mediaStream);
  analyserNode = audioCtx.createAnalyser();
  analyserNode.fftSize = 256;

  // ScriptProcessor for raw PCM capture (works everywhere, no AudioWorklet needed)
  scriptProcessor = audioCtx.createScriptProcessor(4096, 1, 1);

  scriptProcessor.onaudioprocess = (e) => {
    const inputData = e.inputBuffer.getChannelData(0);
    audioBuffer.push(new Float32Array(inputData));

    // VAD: check energy level
    const rms = computeRMS(inputData);
    onVoiceActivity(rms);
  };

  sourceNode.connect(analyserNode);
  analyserNode.connect(scriptProcessor);
  scriptProcessor.connect(audioCtx.destination);

  // Safety max record timer
  maxRecordTimer = setTimeout(() => {
    if (isRecording) stopRecordingAndSend();
  }, MAX_RECORDING_S * 1000);

  startWaveformAnimation();
  setVoiceStatus('recording', '🔴 Listening...');
  setOrbState('recording');
}

function stopRecordingAndSend() {
  if (!isRecording) return;
  isRecording = false;

  clearTimeout(maxRecordTimer);
  clearTimeout(vadSilenceTimer);
  stopWaveformAnimation();
  setOrbState('processing');

  // Disconnect audio nodes
  try {
    scriptProcessor?.disconnect();
    sourceNode?.disconnect();
    analyserNode?.disconnect();
  } catch {}

  if (audioBuffer.length === 0) {
    setVoiceStatus('idle', '🎙️ Hold to speak');
    setOrbState('idle');
    return;
  }

  // Encode and send as WAV
  const wavBuffer = encodeWAV(audioBuffer, SAMPLE_RATE);
  console.log(`[Dorothy Voice] Sending ${wavBuffer.byteLength} bytes of WAV audio.`);
  sendVoiceWSBinary(wavBuffer);
  audioBuffer = [];

  setVoiceStatus('processing', '⚡ Processing...');
}

// ============================================================
// PUSH TO TALK
// ============================================================

async function onMicPressStart(e) {
  e.preventDefault();
  if (isContinuousMode) return; // continuous handles its own flow
  stopAllTTS(); // interrupt Dorothy if she's speaking
  await startRecording();
}

function onMicPressEnd(e) {
  e.preventDefault();
  if (isContinuousMode) return;
  stopRecordingAndSend();
}

// ============================================================
// CONTINUOUS MODE (VAD)
// ============================================================

function toggleContinuousMode() {
  isContinuousMode = !isContinuousMode;
  const toggleBtn = document.getElementById('btn-voice-mode-toggle');
  if (toggleBtn) {
    toggleBtn.textContent = isContinuousMode ? '🔴 LIVE' : '⚪ HOLD';
    toggleBtn.classList.toggle('active', isContinuousMode);
  }

  if (isContinuousMode) {
    setVoiceStatus('ready', '👂 Listening continuously...');
    startContinuousListening();
  } else {
    stopContinuousListening();
    setVoiceStatus('idle', '🎙️ Hold to speak');
  }
}

async function startContinuousListening() {
  await startRecording();
}

function stopContinuousListening() {
  if (isRecording) stopRecordingAndSend();
  isContinuousMode = false;
}

// ── VAD (Voice Activity Detection) ───────────────────────────

function computeRMS(pcmData) {
  let sum = 0;
  for (let i = 0; i < pcmData.length; i++) {
    sum += pcmData[i] * pcmData[i];
  }
  return Math.sqrt(sum / pcmData.length);
}

let vadSpeaking = false;

function onVoiceActivity(rms) {
  if (!isContinuousMode) return;

  if (rms > VAD_ENERGY_THRESH) {
    // Voice detected
    vadSpeaking = true;
    clearTimeout(vadSilenceTimer);
    setOrbState('recording');
  } else if (vadSpeaking) {
    // Silence after voice — start countdown to send
    clearTimeout(vadSilenceTimer);
    vadSilenceTimer = setTimeout(() => {
      if (isRecording && isContinuousMode && vadSpeaking) {
        vadSpeaking = false;
        stopRecordingAndSend();
        // Restart listening after response
        setTimeout(async () => {
          if (isContinuousMode) await startRecording();
        }, 500);
      }
    }, VAD_SILENCE_MS);
  }
}

// ============================================================
// WAV ENCODER
// ============================================================

function encodeWAV(chunks, sampleRate) {
  // Merge Float32Array chunks into one
  const totalLen = chunks.reduce((s, c) => s + c.length, 0);
  const merged = new Float32Array(totalLen);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }

  // Convert Float32 → Int16
  const int16 = new Int16Array(merged.length);
  for (let i = 0; i < merged.length; i++) {
    const s = Math.max(-1, Math.min(1, merged[i]));
    int16[i] = s < 0 ? s * 32768 : s * 32767;
  }

  // WAV header
  const wavHeader = new ArrayBuffer(44);
  const view = new DataView(wavHeader);
  const numChannels = 1;
  const bitsPerSample = 16;
  const byteRate = sampleRate * numChannels * (bitsPerSample / 8);
  const blockAlign = numChannels * (bitsPerSample / 8);
  const dataSize = int16.byteLength;

  function writeStr(v, off, str) {
    for (let i = 0; i < str.length; i++) v.setUint8(off + i, str.charCodeAt(i));
  }

  writeStr(view, 0,  'RIFF');
  view.setUint32(4,  36 + dataSize,   true);
  writeStr(view, 8,  'WAVE');
  writeStr(view, 12, 'fmt ');
  view.setUint32(16, 16,              true);  // PCM chunk size
  view.setUint16(20, 1,               true);  // PCM format
  view.setUint16(22, numChannels,     true);
  view.setUint32(24, sampleRate,      true);
  view.setUint32(28, byteRate,        true);
  view.setUint16(32, blockAlign,      true);
  view.setUint16(34, bitsPerSample,   true);
  writeStr(view, 36, 'data');
  view.setUint32(40, dataSize,        true);

  // Combine header + PCM
  const out = new Uint8Array(44 + dataSize);
  out.set(new Uint8Array(wavHeader), 0);
  out.set(new Uint8Array(int16.buffer), 44);
  return out.buffer;
}

// ============================================================
// STREAMING TTS AUDIO QUEUE
// ============================================================

function enqueueTTS(url) {
  ttsQueue.push(url);
  if (!ttsPlaying) playNextTTS();
}

function playNextTTS() {
  if (ttsQueue.length === 0) {
    ttsPlaying = false;
    ttsCurrentAudio = null;
    setOrbState('idle');
    if (isContinuousMode) {
      // Restart listening after Dorothy finishes speaking
      setTimeout(async () => {
        if (isContinuousMode && !isRecording) await startRecording();
      }, 300);
    }
    return;
  }

  ttsPlaying = true;
  setOrbState('speaking');

  const url = ttsQueue.shift();
  ttsCurrentAudio = new Audio(url);
  ttsCurrentAudio.volume = 1.0;
  ttsCurrentAudio.onended = playNextTTS;
  ttsCurrentAudio.onerror = playNextTTS;
  ttsCurrentAudio.play().catch(() => playNextTTS());
}

function stopAllTTS() {
  ttsQueue.length = 0;
  if (ttsCurrentAudio) {
    ttsCurrentAudio.pause();
    ttsCurrentAudio.src = '';
    ttsCurrentAudio = null;
  }
  ttsPlaying = false;
}

// ============================================================
// WAVEFORM VISUALIZATION
// ============================================================

function startWaveformAnimation() {
  if (!analyserNode || !voiceWaveCanvas || !waveCtx) return;
  const bufLen = analyserNode.frequencyBinCount;
  const dataArr = new Uint8Array(bufLen);

  function draw() {
    if (!isRecording) return;
    animFrame = requestAnimationFrame(draw);
    analyserNode.getByteTimeDomainData(dataArr);

    const W = voiceWaveCanvas.width;
    const H = voiceWaveCanvas.height;
    waveCtx.clearRect(0, 0, W, H);

    // Glow effect
    waveCtx.lineWidth = 2.5;
    waveCtx.strokeStyle = '#00c2ff';
    waveCtx.shadowColor = '#00c2ff';
    waveCtx.shadowBlur = 12;
    waveCtx.beginPath();

    const sliceW = W / bufLen;
    let x = 0;
    for (let i = 0; i < bufLen; i++) {
      const v = dataArr[i] / 128.0;
      const y = (v * H) / 2;
      if (i === 0) waveCtx.moveTo(x, y);
      else waveCtx.lineTo(x, y);
      x += sliceW;
    }
    waveCtx.lineTo(W, H / 2);
    waveCtx.stroke();
  }
  draw();
}

function stopWaveformAnimation() {
  if (animFrame) cancelAnimationFrame(animFrame);
  animFrame = null;
  if (waveCtx && voiceWaveCanvas) {
    waveCtx.clearRect(0, 0, voiceWaveCanvas.width, voiceWaveCanvas.height);
    // Draw flat line
    waveCtx.lineWidth = 1.5;
    waveCtx.strokeStyle = 'rgba(0,194,255,0.25)';
    waveCtx.shadowBlur = 0;
    waveCtx.beginPath();
    waveCtx.moveTo(0, voiceWaveCanvas.height / 2);
    waveCtx.lineTo(voiceWaveCanvas.width, voiceWaveCanvas.height / 2);
    waveCtx.stroke();
  }
}

// ============================================================
// UI STATE HELPERS
// ============================================================

function setBadge(text, color) {
  const badge = document.getElementById('voice-ws-badge');
  if (!badge) return;
  badge.textContent = text;
  badge.style.color = color;
  badge.style.borderColor = color;
}

function setVoiceStatus(status, label) {
  if (voiceStatusLabel) voiceStatusLabel.textContent = label;

  // Update orb subtitle in the main HUD
  const orbSubtitle = document.getElementById('voice-orb-status');
  if (orbSubtitle) orbSubtitle.textContent = label;

  // Update the wave ring animation class
  const waveRing = document.querySelector('.audio-waveform-ring');
  if (waveRing) {
    waveRing.className = `audio-waveform-ring voice-state-${status}`;
  }
}

function setOrbState(state) {
  if (!voiceOrb) return;
  voiceOrb.className = `voice-orb orb-${state}`;
}

function showLiveTranscript(text) {
  if (voiceTranscriptEl) {
    voiceTranscriptEl.textContent = text;
    voiceTranscriptEl.style.opacity = '1';
    // Fade after 4s
    clearTimeout(voiceTranscriptEl._fadeTimer);
    voiceTranscriptEl._fadeTimer = setTimeout(() => {
      voiceTranscriptEl.style.opacity = '0';
    }, 4000);
  }
}

// ============================================================
// BOOT
// ============================================================

window.addEventListener('DOMContentLoaded', initVoiceUI);

// Export for external use
export { enqueueTTS, stopAllTTS, connectVoiceWS, sendVoiceWSText };
