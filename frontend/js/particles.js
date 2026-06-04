/**
 * ParticleSystem Class
 * Spawns a background canvas filled with slow-floating, intelligent molecular particles.
 * Links nearby elements with delicate, fading holographic lines when proximity falls below 120px.
 */
class ParticleSystem {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) {
      console.error(`[ParticleSystem] Canvas element with ID '${canvasId}' not found.`);
      return;
    }
    this.ctx = this.canvas.getContext('2d');
    this.particles = [];
    this.numParticles = 80;
    this.connectionDistance = 120; // connection bounds
    this.animationFrameId = null;

    this.resizeCanvas();
    window.addEventListener('resize', () => this.resizeCanvas());

    this.init();
    this.start();
  }

  /**
   * Adjust particle canvas sizing
   */
  resizeCanvas() {
    this.canvas.width = window.innerWidth;
    this.canvas.height = window.innerHeight;
  }

  /**
   * Generate static coordinate points
   */
  init() {
    this.particles = [];
    const w = this.canvas.width;
    const h = this.canvas.height;
    
    for (let i = 0; i < this.numParticles; i++) {
      this.particles.push({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.35, // slow drifting velocity
        vy: (Math.random() - 0.5) * 0.35,
        radius: Math.random() * 1.5 + 0.5
      });
    }
  }

  /**
   * Start loop
   */
  start() {
    const render = () => {
      this.update();
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
   * Move elements inside window bounds
   */
  update() {
    const w = this.canvas.width;
    const h = this.canvas.height;

    this.particles.forEach(p => {
      p.x += p.vx;
      p.y += p.vy;

      // Bounce/teleport bounds mapping
      if (p.x < 0) p.x = w;
      if (p.x > w) p.x = 0;
      if (p.y < 0) p.y = h;
      if (p.y > h) p.y = 0;
    });
  }

  /**
   * Draw dots and webbing
   */
  draw() {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;

    // Fully clear screen (transparent overlay to let css background gradient shine through)
    ctx.clearRect(0, 0, w, h);

    // 1. Draw web connection strands
    ctx.lineWidth = 0.5;
    for (let i = 0; i < this.numParticles; i++) {
      const p1 = this.particles[i];
      for (let j = i + 1; j < this.numParticles; j++) {
        const p2 = this.particles[j];
        
        // Fast delta check
        const dx = p1.x - p2.x;
        const dy = p1.y - p2.y;
        
        // Skip connections if delta-X or delta-Y exceeds max distance (performance optimization)
        if (Math.abs(dx) > this.connectionDistance || Math.abs(dy) > this.connectionDistance) {
          continue;
        }

        const distSq = dx * dx + dy * dy;
        const maxDistSq = this.connectionDistance * this.connectionDistance;

        if (distSq < maxDistSq) {
          const dist = Math.sqrt(distSq);
          // Opacity decreases linearly with distance
          const alpha = (1 - (dist / this.connectionDistance)) * 0.15;
          ctx.strokeStyle = `rgba(0, 255, 255, ${alpha})`;
          
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.stroke();
        }
      }
    }

    // 2. Draw solid particles
    ctx.fillStyle = 'rgba(0, 255, 255, 0.45)';
    ctx.shadowBlur = 4;
    ctx.shadowColor = 'rgba(0, 255, 255, 0.5)';
    
    for (let i = 0; i < this.numParticles; i++) {
      const p = this.particles[i];
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}
