/**
 * ArcReactor Class
 * Renders a highly interactive, animated Iron Man style Arc Reactor on Canvas.
 * Supports multiple rotating segmented rings, custom data points, accent arcs, and thinking speed pulse adjustments.
 */
class ArcReactor {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) {
      console.error(`[ArcReactor] Canvas element with ID '${canvasId}' not found.`);
      return;
    }
    this.ctx = this.canvas.getContext('2d');
    this.isThinking = false;
    this.animationFrameId = null;
    
    // Animation rotation angles
    this.angle1 = 0;
    this.angle2 = 0;
    this.angle3 = 0;
    
    // Core glow pulse oscillator
    this.pulseVal = 0;
    
    // Start animation loop
    this.start();
  }

  /**
   * Toggle thinking mode (speeds up rotation and pulses core brightness)
   * @param {boolean} status - Thinking state
   */
  setThinking(status) {
    this.isThinking = !!status;
  }

  /**
   * Start rendering loop
   */
  start() {
    const render = () => {
      this.draw();
      this.animationFrameId = requestAnimationFrame(render);
    };
    render();
  }

  /**
   * Stop rendering loop
   */
  stop() {
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
    }
  }

  /**
   * Clear and draw reactor components
   */
  draw() {
    const ctx = this.ctx;
    const canvas = this.canvas;
    const width = canvas.width;
    const height = canvas.height;
    const cx = width / 2;
    const cy = height / 2;
    
    // Smooth clear (subtle trail effect by painting transparent black)
    ctx.fillStyle = 'rgba(5, 8, 22, 0.25)';
    ctx.fillRect(0, 0, width, height);

    // Speed multiplier depending on Jarvis state
    const speedMult = this.isThinking ? 4.5 : 1.0;
    const pulseSpeed = this.isThinking ? 0.15 : 0.04;
    
    // Update rotation angles
    this.angle1 += 0.005 * speedMult;     // Inner ring (clockwise)
    this.angle2 -= 0.008 * speedMult;     // Middle ring (counter-clockwise)
    this.angle3 += 0.003 * speedMult;     // Outer ring (clockwise)
    
    // Update pulse oscillator
    this.pulseVal += pulseSpeed;
    const pulseFactor = Math.sin(this.pulseVal) * 0.25 + 0.75; // Cycles between 0.5 and 1.0

    // Save context
    ctx.save();
    
    // Enable glowing composites
    ctx.shadowBlur = 15;
    ctx.shadowColor = 'rgba(0, 255, 255, 0.4)';

    // --- DRAW 1: THE CORE RADIAL GLOW ---
    const coreRadius = 40 * (this.isThinking ? pulseFactor * 1.1 : 1.0);
    const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreRadius);
    gradient.addColorStop(0, '#FFFFFF');
    gradient.addColorStop(0.2, 'rgba(0, 255, 255, 0.9)');
    gradient.addColorStop(0.5, 'rgba(0, 212, 255, 0.5)');
    gradient.addColorStop(1, 'rgba(0, 255, 255, 0)');
    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(cx, cy, coreRadius, 0, Math.PI * 2);
    ctx.fill();

    // --- DRAW 2: INNER ROTATING RING (Segmented) ---
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(this.angle1);
    
    ctx.strokeStyle = 'rgba(0, 255, 255, 0.6)';
    ctx.lineWidth = 3;
    const innerRadius = 65;
    const segmentCount = 6;
    const segmentGap = 0.25; // angle in radians
    const segmentLength = (Math.PI * 2) / segmentCount - segmentGap;
    
    for (let i = 0; i < segmentCount; i++) {
      const startAngle = i * (segmentLength + segmentGap);
      const endAngle = startAngle + segmentLength;
      ctx.beginPath();
      ctx.arc(0, 0, innerRadius, startAngle, endAngle);
      ctx.stroke();
      
      // Draw a small node point at the end of each segment
      const endX = Math.cos(endAngle) * innerRadius;
      const endY = Math.sin(endAngle) * innerRadius;
      ctx.fillStyle = '#00FFFF';
      ctx.beginPath();
      ctx.arc(endX, endY, 3, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();

    // --- DRAW 3: MIDDLE ROTATING RING (Accent Ring) ---
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(this.angle2);
    
    const middleRadius = 100;
    
    // Cyan segments
    ctx.strokeStyle = 'rgba(0, 255, 255, 0.3)';
    ctx.lineWidth = 5;
    ctx.beginPath();
    ctx.arc(0, 0, middleRadius, 0, Math.PI * 1.2);
    ctx.stroke();
    
    ctx.beginPath();
    ctx.arc(0, 0, middleRadius, Math.PI * 1.3, Math.PI * 1.8);
    ctx.stroke();
    
    // Orange glowing accent segment
    ctx.shadowColor = 'rgba(255, 107, 53, 0.6)';
    ctx.strokeStyle = '#ff6b35';
    ctx.lineWidth = 6;
    ctx.beginPath();
    ctx.arc(0, 0, middleRadius, Math.PI * 1.85, Math.PI * 2);
    ctx.stroke();
    
    // Tiny structural ticks inside middle ring
    ctx.strokeStyle = 'rgba(0, 255, 255, 0.15)';
    ctx.lineWidth = 2;
    for (let j = 0; j < 12; j++) {
      const tickAngle = (j * Math.PI * 2) / 12;
      const tickStart = middleRadius - 8;
      const tickEnd = middleRadius - 2;
      ctx.beginPath();
      ctx.moveTo(Math.cos(tickAngle) * tickStart, Math.sin(tickAngle) * tickStart);
      ctx.lineTo(Math.cos(tickAngle) * tickEnd, Math.sin(tickAngle) * tickEnd);
      ctx.stroke();
    }
    ctx.restore();

    // --- DRAW 4: OUTER ROTATING RING WITH TICK MARKS ---
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(this.angle3);
    
    const outerRadius = 140;
    ctx.strokeStyle = 'rgba(0, 255, 255, 0.15)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(0, 0, outerRadius, 0, Math.PI * 2);
    ctx.stroke();

    // Outer peripheral ticks & blocks
    const tickCount = 60;
    ctx.strokeStyle = 'rgba(0, 255, 255, 0.4)';
    for (let k = 0; k < tickCount; k++) {
      const angle = (k * Math.PI * 2) / tickCount;
      const isMajor = k % 5 === 0;
      const tickLen = isMajor ? 12 : 5;
      ctx.lineWidth = isMajor ? 2.0 : 0.8;
      
      if (isMajor) {
        ctx.strokeStyle = 'rgba(0, 255, 255, 0.6)';
      } else {
        ctx.strokeStyle = 'rgba(0, 255, 255, 0.2)';
      }
      
      const startR = outerRadius + 3;
      const endR = startR + tickLen;
      
      ctx.beginPath();
      ctx.moveTo(Math.cos(angle) * startR, Math.sin(angle) * startR);
      ctx.lineTo(Math.cos(angle) * endR, Math.sin(angle) * endR);
      ctx.stroke();
      
      // Draw tiny hex labels or numbers on outer ticks
      if (isMajor && k % 15 === 0) {
        ctx.font = '7px Share Tech Mono';
        ctx.fillStyle = 'rgba(0, 255, 255, 0.7)';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const textDist = endR + 10;
        const textVal = `${(k * 6).toString().padStart(3, '0')}`;
        ctx.fillText(textVal, Math.cos(angle) * textDist, Math.sin(angle) * textDist);
      }
    }
    
    // Add two prominent yellow/orange indicator markers
    ctx.fillStyle = '#ffaa00';
    ctx.shadowColor = 'rgba(255, 170, 0, 0.6)';
    ctx.beginPath();
    ctx.arc(Math.cos(0.2) * (outerRadius + 3), Math.sin(0.2) * (outerRadius + 3), 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(Math.cos(Math.PI) * (outerRadius + 3), Math.sin(Math.PI) * (outerRadius + 3), 4, 0, Math.PI * 2);
    ctx.fill();
    
    ctx.restore();

    // --- DRAW 5: STRUCTURAL HUD STENCIL ELEMENTS (Stationary) ---
    // Hexagonal bounds around reactor center
    ctx.strokeStyle = 'rgba(0, 255, 255, 0.08)';
    ctx.lineWidth = 1;
    ctx.shadowBlur = 0;
    ctx.beginPath();
    const hexRadius = 175;
    for (let h = 0; h < 6; h++) {
      const angle = (h * Math.PI) / 3;
      const x = cx + Math.cos(angle) * hexRadius;
      const y = cy + Math.sin(angle) * hexRadius;
      if (h === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.stroke();

    // Crosshairs
    ctx.strokeStyle = 'rgba(0, 255, 255, 0.06)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(cx - hexRadius, cy);
    ctx.lineTo(cx - 150, cy);
    ctx.moveTo(cx + 150, cy);
    ctx.lineTo(cx + hexRadius, cy);
    ctx.moveTo(cx, cy - hexRadius);
    ctx.lineTo(cx, cy - 150);
    ctx.moveTo(cx, cy + 150);
    ctx.lineTo(cx, cy + hexRadius);
    ctx.stroke();

    ctx.restore();
  }
}
