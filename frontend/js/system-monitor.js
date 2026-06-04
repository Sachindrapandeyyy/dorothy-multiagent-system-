/**
 * SystemMonitor Class
 * Renders multiple circular canvas gauge components representing telemetry for CPU, RAM, and Disk.
 * Handles styling transitions based on resource load, network speed reporting, and battery status blocks.
 */
class SystemMonitor {
  constructor() {
    this.gauges = {
      cpu: {
        canvas: document.getElementById('cpu-gauge'),
        currentVal: 0,
        targetVal: 0,
        label: 'CPU'
      },
      ram: {
        canvas: document.getElementById('ram-gauge'),
        currentVal: 0,
        targetVal: 0,
        label: 'RAM'
      },
      disk: {
        canvas: document.getElementById('disk-gauge'),
        currentVal: 0,
        targetVal: 0,
        label: 'DISK'
      }
    };

    this.uploadSpeedElement = document.getElementById('net-upload-val');
    this.downloadSpeedElement = document.getElementById('net-download-val');
    this.batteryBarElement = document.getElementById('battery-level-bar');
    this.batteryPercentElement = document.getElementById('battery-percent-val');
    this.batteryPanel = document.getElementById('battery-panel');

    // Makecircular canvas gauges interactive click diagnostics
    this.initInteractiveGauges();

    // Run custom drawing loop for gauge value smoothing
    this.startDrawLoop();
  }

  /**
   * Bind interactive click event listeners onCircular Canvas Gauges
   */
  initInteractiveGauges() {
    if (this.gauges.cpu.canvas) {
      this.gauges.cpu.canvas.style.cursor = 'pointer';
      this.gauges.cpu.canvas.title = "Click to run diagnostic processes CPU load";
      this.gauges.cpu.canvas.addEventListener('click', () => {
        console.log("[HUD System] CPU Gauge clicked. Executing process load subshell...");
        if (window.socket) {
          window.socket.send('command', { 
            action: 'execute_terminal', 
            command: 'powershell -Command "Get-Process | Sort-Object CPU -Descending | Select-Object -First 5 -Property ProcessName, CPU"' 
          });
          if (window.agentDashboard) {
            window.agentDashboard.addActivity("CPU Diagnostic subshell initiated by click telemetry.", "SIR");
          }
        }
      });
    }

    if (this.gauges.ram.canvas) {
      this.gauges.ram.canvas.style.cursor = 'pointer';
      this.gauges.ram.canvas.title = "Click to run diagnostic RAM load allocations";
      this.gauges.ram.canvas.addEventListener('click', () => {
        console.log("[HUD System] RAM Gauge clicked. Executing RAM load subshell...");
        if (window.socket) {
          window.socket.send('command', { 
            action: 'execute_terminal', 
            command: 'powershell -Command "Get-Process | Sort-Object WS -Descending | Select-Object -First 5 | ForEach-Object { [PSCustomObject]@{ ProcessName = $_.ProcessName; WorkingSet_MB = [math]::Round($_.WS / 1MB, 1) } }"' 
          });
          if (window.agentDashboard) {
            window.agentDashboard.addActivity("RAM Allocation diagnostics initiated by click telemetry.", "SIR");
          }
        }
      });
    }

    if (this.gauges.disk.canvas) {
      this.gauges.disk.canvas.style.cursor = 'pointer';
      this.gauges.disk.canvas.title = "Click to query detailed active disk partition stats";
      this.gauges.disk.canvas.addEventListener('click', () => {
        console.log("[HUD System] Disk Gauge clicked. Querying logical drives...");
        if (window.socket) {
          window.socket.send('command', { 
            action: 'execute_terminal', 
            command: 'powershell -Command "Get-Volume | Select-Object DriveLetter, FriendlyName, SizeRemaining, Size | ForEach-Object { [PSCustomObject]@{ Drive = $_.DriveLetter; Name = $_.FriendlyName; Free_GB = [math]::Round($_.SizeRemaining / 1GB, 1); Size_GB = [math]::Round($_.Size / 1GB, 1) } }"' 
          });
          if (window.agentDashboard) {
            window.agentDashboard.addActivity("Disk Volume diagnostic query initiated by click.", "SIR");
          }
        }
      });
    }
  }

  /**
   * Update internal telemetry values and DOM elements
   * @param {object} stats - System stats parsed from WebSocket (CPU, RAM, Disk, battery, network)
   */
  update(stats) {
    if (!stats) return;

    // 1. Target values update (for smooth interpolation)
    if (typeof stats.cpu !== 'undefined') {
      this.gauges.cpu.targetVal = stats.cpu;
    }
    if (stats.ram && typeof stats.ram.percent !== 'undefined') {
      this.gauges.ram.targetVal = stats.ram.percent;
    }
    if (stats.disk && stats.disk.length > 0) {
      // Use average or drive C: percent
      const primaryDrive = stats.disk.find(d => d.drive === 'C:') || stats.disk[0];
      if (primaryDrive && typeof primaryDrive.percent !== 'undefined') {
        this.gauges.disk.targetVal = primaryDrive.percent;
      }
    }

    // 2. Network speed metrics formatting
    if (stats.network) {
      const up = stats.network.upload_kbps;
      const down = stats.network.download_kbps;
      
      if (this.uploadSpeedElement) {
        this.uploadSpeedElement.innerText = up > 1024 
          ? `▲ ${(up / 1024).toFixed(1)} MB/s` 
          : `▲ ${up.toFixed(1)} KB/s`;
      }
      if (this.downloadSpeedElement) {
        this.downloadSpeedElement.innerText = down > 1024 
          ? `▼ ${(down / 1024).toFixed(1)} MB/s` 
          : `▼ ${down.toFixed(1)} KB/s`;
      }
    }

    // 3. Battery statistics rendering
    if (stats.battery) {
      if (this.batteryPanel) this.batteryPanel.style.display = 'flex';
      const pct = stats.battery.percent || 0;
      
      if (this.batteryBarElement) {
        this.batteryBarElement.style.width = `${pct}%`;
        
        // Colors for power state
        if (stats.battery.charging) {
          this.batteryBarElement.style.backgroundColor = 'var(--hud-green)';
        } else if (pct < 20) {
          this.batteryBarElement.style.backgroundColor = 'var(--hud-red)';
        } else {
          this.batteryBarElement.style.backgroundColor = 'var(--hud-cyan)';
        }
      }
      
      if (this.batteryPercentElement) {
        this.batteryPercentElement.innerText = stats.battery.charging 
          ? `CHARGING (${pct}%)` 
          : `${pct}%`;
      }
    } else {
      if (this.batteryPanel) this.batteryPanel.style.display = 'none';
    }
  }

  /**
   * Draws a gauge on a canvas using currentVal
   */
  drawGauge(gauge) {
    const canvas = gauge.canvas;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    const cx = w / 2;
    const cy = h / 2;
    const radius = w / 2 - 12;

    ctx.clearRect(0, 0, w, h);

    // Style threshold variables
    let strokeColor = 'var(--hud-cyan)';
    let shadowColor = 'rgba(0, 255, 255, 0.4)';
    const val = gauge.currentVal;

    if (val >= 90) {
      strokeColor = 'var(--hud-red)';
      shadowColor = 'rgba(255, 51, 68, 0.5)';
    } else if (val >= 80) {
      strokeColor = 'var(--hud-orange)';
      shadowColor = 'rgba(255, 107, 53, 0.5)';
    }

    // 1. Background full gray track circle
    ctx.strokeStyle = 'rgba(0, 255, 255, 0.05)';
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.stroke();

    // 2. Active HUD segment arc
    ctx.save();
    ctx.shadowBlur = 8;
    ctx.shadowColor = shadowColor;
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = 5;
    ctx.lineCap = 'round';
    
    // Start from top (-90 degrees)
    const startAngle = -Math.PI / 2;
    const endAngle = startAngle + (val / 100) * (Math.PI * 2);
    
    ctx.beginPath();
    ctx.arc(cx, cy, radius, startAngle, endAngle);
    ctx.stroke();
    ctx.restore();

    // 3. Peripheral ticking marks
    ctx.strokeStyle = 'rgba(0, 255, 255, 0.15)';
    ctx.lineWidth = 1;
    const numTicks = 30;
    for (let i = 0; i < numTicks; i++) {
      const angle = (i * Math.PI * 2) / numTicks;
      const tickStart = radius + 3;
      const tickEnd = radius + 6;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(angle) * tickStart, cy + Math.sin(angle) * tickStart);
      ctx.lineTo(cx + Math.cos(angle) * tickEnd, cy + Math.sin(angle) * tickEnd);
      ctx.stroke();
    }

    // 4. Center telemetry percentage text
    ctx.font = '800 1.25rem Orbitron';
    ctx.fillStyle = strokeColor === 'var(--hud-cyan)' ? 'var(--hud-white)' : strokeColor;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.shadowBlur = 4;
    ctx.shadowColor = shadowColor;
    
    ctx.fillText(`${Math.round(val)}%`, cx, cy - 2);

    // 5. Base metric identifier label inside gauge bounds
    ctx.font = '600 0.55rem Orbitron';
    ctx.fillStyle = 'var(--hud-text-dim)';
    ctx.shadowBlur = 0;
    ctx.fillText(gauge.label, cx, cy + 16);
  }

  /**
   * Start 60fps gauge redraw loop with smooth lerping values
   */
  startDrawLoop() {
    const loop = () => {
      Object.keys(this.gauges).forEach(key => {
        const g = this.gauges[key];
        // Linear interpolation (lerp) for smooth gauge transition animations
        const diff = g.targetVal - g.currentVal;
        if (Math.abs(diff) > 0.05) {
          g.currentVal += diff * 0.08;
        } else {
          g.currentVal = g.targetVal;
        }
        this.drawGauge(g);
      });
      requestAnimationFrame(loop);
    };
    loop();
  }
}
