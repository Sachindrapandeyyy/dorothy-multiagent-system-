/**
 * NeuralNetwork Class
 * Visualizes a multi-layered neural network on Canvas.
 * Models layers, node grids, interconnecting synapses, traveling pulse waves,
 * and high-activity cascade triggers during active JARVIS thinking.
 */
class NeuralNetwork {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) {
      console.error(`[NeuralNetwork] Canvas element with ID '${canvasId}' not found.`);
      return;
    }
    this.ctx = this.canvas.getContext('2d');
    this.isThinking = false;
    this.animationFrameId = null;
    
    // Layer structure: 5 layers representing nodes
    this.layerSizes = [5, 8, 6, 4, 2];
    this.nodes = [];
    this.pulses = [];
    this.pulseIdCounter = 0;
    
    this.resizeCanvas();
    window.addEventListener('resize', () => this.resizeCanvas());
    
    // Generate static architecture
    this.initNetwork();
    
    // Start animation loop
    this.start();
  }

  /**
   * Adjust canvas coordinate mapping
   */
  resizeCanvas() {
    const parent = this.canvas.parentElement;
    this.canvas.width = parent.clientWidth;
    this.canvas.height = parent.clientHeight || 180;
  }

  /**
   * Initialize nodes grid in layers
   */
  initNetwork() {
    this.nodes = [];
    this.pulses = [];
    const layersCount = this.layerSizes.length;
    
    for (let l = 0; l < layersCount; l++) {
      const size = this.layerSizes[l];
      const layerNodes = [];
      
      for (let n = 0; n < size; n++) {
        layerNodes.push({
          // Node metadata
          layer: l,
          index: n,
          activity: 0.1, // normal low energy state
          color: l === 0 ? 'var(--hud-cyan)' : (l === layersCount - 1 ? 'var(--hud-orange)' : 'var(--hud-cyan-bright)')
        });
      }
      this.nodes.push(layerNodes);
    }
  }

  /**
   * Activate active thinking state
   */
  startThinking() {
    this.isThinking = true;
  }

  /**
   * Deactivate active thinking state
   */
  stopThinking() {
    this.isThinking = false;
    // reset activity of all nodes smoothly
    this.nodes.forEach(layer => {
      layer.forEach(n => {
        n.activity = 0.1;
      });
    });
    this.pulses = [];
  }

  /**
   * Spawn a signal pulse from Layer L node to L+1 node
   */
  spawnPulse(fromLayer, fromIdx, toIdx) {
    this.pulses.push({
      id: this.pulseIdCounter++,
      fromLayer,
      fromIdx,
      toIdx,
      progress: 0,
      speed: 0.02 + Math.random() * 0.015
    });
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
   * Calculate nodes positioning
   */
  getNodePos(layerIdx, nodeIdx) {
    const w = this.canvas.width;
    const h = this.canvas.height;
    const paddingX = 40;
    const paddingY = 20;
    
    // Spread layers evenly across width
    const layersCount = this.layerSizes.length;
    const x = paddingX + (layerIdx / (layersCount - 1)) * (w - 2 * paddingX);
    
    // Spread nodes evenly vertically inside layer
    const nodesCount = this.layerSizes[layerIdx];
    let y;
    if (nodesCount === 1) {
      y = h / 2;
    } else {
      y = paddingY + (nodeIdx / (nodesCount - 1)) * (h - 2 * paddingY);
    }
    
    return { x, y };
  }

  /**
   * Logic updates for signals and pulses
   */
  update() {
    if (this.isThinking) {
      // Spawn new pulses randomly at layer 0
      if (Math.random() < 0.15 && this.pulses.length < 35) {
        const fromIdx = Math.floor(Math.random() * this.layerSizes[0]);
        const toIdx = Math.floor(Math.random() * this.layerSizes[1]);
        this.spawnPulse(0, fromIdx, toIdx);
      }

      // Randomly ignite node activity triggers
      this.nodes.forEach(layer => {
        layer.forEach(n => {
          if (Math.random() < 0.03) {
            n.activity = 0.5 + Math.random() * 0.5;
          } else {
            // Decay node activity
            n.activity += (0.1 - n.activity) * 0.08;
          }
        });
      });
    } else {
      // Idle slow glow pulses
      if (Math.random() < 0.02 && this.pulses.length < 3) {
        const fromIdx = Math.floor(Math.random() * this.layerSizes[0]);
        const toIdx = Math.floor(Math.random() * this.layerSizes[1]);
        this.spawnPulse(0, fromIdx, toIdx);
      }
      this.nodes.forEach(layer => {
        layer.forEach(n => {
          n.activity += (0.08 - n.activity) * 0.05;
        });
      });
    }

    // Process active traveling signal pulses
    for (let i = this.pulses.length - 1; i >= 0; i--) {
      const p = this.pulses[i];
      p.progress += p.speed;
      
      // Target destination reached?
      if (p.progress >= 1) {
        // Ignite the target node activity
        const targetLayer = p.fromLayer + 1;
        if (targetLayer < this.layerSizes.length) {
          const targetNode = this.nodes[targetLayer][p.toIdx];
          if (targetNode) {
            targetNode.activity = 0.9;
            
            // Cascade: forward pulse to next layer
            if (this.isThinking && targetLayer < this.layerSizes.length - 1) {
              const branches = Math.random() < 0.6 ? 2 : 1;
              for (let b = 0; b < branches; b++) {
                const nextSize = this.layerSizes[targetLayer + 1];
                const nextIdx = Math.floor(Math.random() * nextSize);
                this.spawnPulse(targetLayer, p.toIdx, nextIdx);
              }
            }
          }
        }
        // Remove completed pulse
        this.pulses.splice(i, 1);
      }
    }
  }

  /**
   * Render connection synapses and nodes
   */
  draw() {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;
    
    ctx.clearRect(0, 0, w, h);
    
    // Draw grid overlay behind nodes
    ctx.strokeStyle = 'rgba(0, 255, 255, 0.02)';
    ctx.lineWidth = 0.5;
    const gridSpacing = 20;
    for (let x = 0; x < w; x += gridSpacing) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y < h; y += gridSpacing) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    // --- DRAW CONNECTIONS (SYNAPSES) ---
    for (let l = 0; l < this.layerSizes.length - 1; l++) {
      const size1 = this.layerSizes[l];
      const size2 = this.layerSizes[l + 1];
      
      for (let n1 = 0; n1 < size1; n1++) {
        const p1 = this.getNodePos(l, n1);
        
        for (let n2 = 0; n2 < size2; n2++) {
          const p2 = this.getNodePos(l + 1, n2);
          
          // Synapse opacity depends on whether JARVIS is thinking or idle
          ctx.strokeStyle = this.isThinking 
            ? 'rgba(0, 255, 255, 0.08)' 
            : 'rgba(0, 255, 255, 0.03)';
          ctx.lineWidth = 0.8;
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.stroke();
        }
      }
    }

    // --- DRAW ACTIVE TRAVELING PULSES ---
    ctx.save();
    ctx.shadowBlur = 8;
    ctx.shadowColor = 'rgba(0, 255, 255, 0.8)';
    this.pulses.forEach(p => {
      const p1 = this.getNodePos(p.fromLayer, p.fromIdx);
      const p2 = this.getNodePos(p.fromLayer + 1, p.toIdx);
      
      // Interpolate position along synapse
      const px = p1.x + (p2.x - p1.x) * p.progress;
      const py = p1.y + (p2.y - p1.y) * p.progress;
      
      ctx.fillStyle = p.fromLayer === this.layerSizes.length - 2 
        ? '#ff6b35' 
        : '#00FFFF';
      ctx.beginPath();
      ctx.arc(px, py, 2.5, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.restore();

    // --- DRAW LAYER NODES ---
    ctx.save();
    for (let l = 0; l < this.nodes.length; l++) {
      for (let n = 0; n < this.nodes[l].length; n++) {
        const node = this.nodes[l][n];
        const pos = this.getNodePos(l, n);
        
        // Node outer glow
        const glowRadius = 4 + node.activity * 5;
        const colorVal = node.color;
        
        ctx.shadowBlur = node.activity * 12;
        ctx.shadowColor = colorVal.includes('orange') ? 'rgba(255, 107, 53, 0.8)' : 'rgba(0, 255, 255, 0.8)';
        
        // Outer pulsing ring
        ctx.strokeStyle = colorVal.includes('orange') 
          ? `rgba(255, 107, 53, ${0.2 + node.activity * 0.8})` 
          : `rgba(0, 255, 255, ${0.2 + node.activity * 0.8})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, glowRadius + 2, 0, Math.PI * 2);
        ctx.stroke();

        // Inner solid core
        ctx.fillStyle = colorVal.includes('orange') ? '#ff6b35' : '#00FFFF';
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, 3, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.restore();
  }
}
