/**
 * AudioVisualizer Class
 * Renders an advanced horizontal frequency bar graph at the bottom strip.
 * Transitions between slow, rolling ambient sine waves in idle state and
 * rapid sound-wave frequency responses when speech audio (TTS) is playing.
 */
class AudioVisualizer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) {
      console.error(`[AudioVisualizer] Canvas element with ID '${canvasId}' not found.`);
      return;
    }
    this.ctx = this.canvas.getContext('2d');
    this.isActive = false;
    this.animationFrameId = null;
    
    // Waveform simulation properties
    this.phase = 0;
    this.simulationTime = 0;
    this.simulatedBars = [];
    this.numBars = 120;
    this.audioContext = null;
    this.analyser = null;
    
    this.resizeCanvas();
    window.addEventListener('resize', () => this.resizeCanvas());

    // Initialize mock array elements
    for (let i = 0; i < this.numBars; i++) {
      this.simulatedBars.push(2); // start flat
    }

    // Start drawing loop
    this.start();
  }

  /**
   * Resize to fill footer boundary width
   */
  resizeCanvas() {
    const parent = this.canvas.parentElement;
    this.canvas.width = parent.clientWidth;
    this.canvas.height = parent.clientHeight || 30;
  }

  /**
   * Set active voice telemetry state
   * @param {boolean} active - Talking or silent
   */
  setActive(active) {
    this.isActive = !!active;
    if (!this.isActive) {
      this.simulationTime = 0;
    }
  }

  /**
   * Simulate a speech waveform reaction from incoming text length
   */
  simulateSpeech(text = '') {
    this.setActive(true);
    // Maintain talking bars simulation for roughly 1.5s + based on text size
    const estimatedDuration = Math.max(1500, text.length * 75);
    
    if (this.speechTimeout) clearTimeout(this.speechTimeout);
    this.speechTimeout = setTimeout(() => {
      this.setActive(false);
    }, estimatedDuration);
  }

  /**
   * Start loop
   */
  start() {
    const render = () => {
      this.draw();
      this.animationFrameId = requestAnimationFrame(render);
    };
    render();
  }

  /**
   * Stop loop
   */
  stop() {
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
    }
  }

  /**
   * Draw visualizer curves and glows
   */
  draw() {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;
    
    ctx.clearRect(0, 0, w, h);
    
    const barWidth = Math.max(2, Math.floor(w / this.numBars) - 2);
    const spacing = 3;
    const startX = (w - (this.numBars * (barWidth + spacing))) / 2;

    ctx.save();
    // Glowing gradient
    const gradient = ctx.createLinearGradient(0, h, 0, 0);
    gradient.addColorStop(0, 'rgba(0, 212, 255, 0.15)');
    gradient.addColorStop(0.5, 'rgba(0, 255, 255, 0.8)');
    gradient.addColorStop(1, '#FFFFFF');

    ctx.fillStyle = gradient;
    ctx.shadowBlur = 10;
    ctx.shadowColor = 'rgba(0, 255, 255, 0.6)';

    this.phase += 0.05; // speed of ambient wave

    // Draw bars
    for (let i = 0; i < this.numBars; i++) {
      let targetHeight = 2; // default flat

      if (this.isActive) {
        // --- REACTIVE FREQUENCY SPEECH SIMULATION ---
        this.simulationTime += 0.001;
        // Layered high frequencies + noise
        const wave1 = Math.sin(i * 0.12 + this.phase * 2.5) * 12;
        const wave2 = Math.cos(i * 0.06 - this.phase * 1.8) * 8;
        const randomNoise = Math.random() * 6;
        
        // Window function (taper height towards left and right edges)
        const windowFactor = Math.sin((i / this.numBars) * Math.PI);
        
        targetHeight = Math.max(2, (10 + wave1 + wave2 + randomNoise) * windowFactor * 1.1);
      } else {
        // --- AMBIENT IDLE SINE WAVE ---
        const wave = Math.sin(i * 0.05 + this.phase) * 3.5;
        const waveSlow = Math.cos(i * 0.1 - this.phase * 0.3) * 2;
        const windowFactor = Math.sin((i / this.numBars) * Math.PI);
        
        targetHeight = Math.max(1, (3 + wave + waveSlow) * windowFactor);
      }

      // Smoothly interpolate current heights
      const diff = targetHeight - this.simulatedBars[i];
      this.simulatedBars[i] += diff * 0.2; // quick lerping

      const currentHeight = this.simulatedBars[i];
      const x = startX + i * (barWidth + spacing);
      const y = h - currentHeight;

      // Draw rounded capsule bars
      ctx.beginPath();
      if (ctx.roundRect) {
        ctx.roundRect(x, y, barWidth, currentHeight, 1);
      } else {
        ctx.rect(x, y, barWidth, currentHeight);
      }
      ctx.fill();
    }

    ctx.restore();
  }
}
