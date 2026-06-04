class JarvisGlobe {
  constructor(canvasId, containerId, onCountrySelected) {
    this.canvas = document.getElementById(canvasId);
    this.container = document.getElementById(containerId);
    this.onCountrySelected = onCountrySelected;
    
    if (!this.canvas || !this.container) {
      console.error("Globe canvas or container not found.");
      return;
    }

    this.width = this.container.clientWidth;
    this.height = this.container.clientHeight;
    
    // Country coordinates (Latitude, Longitude)
    this.countries = [
      { name: "India", lat: 20.5937, lon: 78.9629, desc: "South Asian Tactical Sector" },
      { name: "USA", lat: 37.0902, lon: -95.7129, desc: "North American Strategic Base" },
      { name: "United Kingdom", lat: 55.3781, lon: -3.4360, desc: "European Western Division" },
      { name: "Japan", lat: 36.2048, lon: 138.2529, desc: "Eastern Technology Corridor" },
      { name: "Australia", lat: -25.2744, lon: 133.7751, desc: "Southern Pacific Hub" },
      { name: "Germany", lat: 51.1657, lon: 10.4515, desc: "Central European Matrix" },
      { name: "Brazil", lat: -14.2350, lon: -51.9253, desc: "South American Sector" },
      { name: "South Africa", lat: -30.5595, lon: 22.9375, desc: "African Southern Portal" }
    ];

    this.markers = [];
    this.init();
    this.animate();
    
    // Handle resizing
    window.addEventListener("resize", () => this.onResize());
  }

  init() {
    // 1. Scene, Camera, Renderer
    this.scene = new THREE.Scene();
    
    this.camera = new THREE.PerspectiveCamera(45, this.width / this.height, 0.1, 1000);
    this.camera.position.z = 8;
    
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
      alpha: true
    });
    this.renderer.setSize(this.width, this.height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    // 2. Earth Geometry (Holographic Wireframe)
    this.globeRadius = 3;
    const geometry = new THREE.SphereGeometry(this.globeRadius, 30, 30);
    
    // Glowing cyan wireframe material
    const material = new THREE.MeshBasicMaterial({
      color: 0x00ffff,
      wireframe: true,
      transparent: true,
      opacity: 0.12
    });
    
    this.globeMesh = new THREE.Mesh(geometry, material);
    this.scene.add(this.globeMesh);

    // 3. Vertex Dots (Point Cloud overlays)
    const pointsMaterial = new THREE.PointsMaterial({
      color: 0x00e5ff,
      size: 0.04,
      transparent: true,
      opacity: 0.4
    });
    const globePoints = new THREE.Points(geometry, pointsMaterial);
    this.globeMesh.add(globePoints);

    // 4. Emissive Outer Ring (Holo Ring Orbit)
    const ringGeo = new THREE.RingGeometry(this.globeRadius + 0.3, this.globeRadius + 0.35, 64);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x00ffff,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.08
    });
    this.orbitRing = new THREE.Mesh(ringGeo, ringMat);
    this.orbitRing.rotation.x = Math.PI / 2;
    this.scene.add(this.orbitRing);

    // 5. Build Country pinpoints
    this.countries.forEach(country => {
      const position = this.latLonToVector3(country.lat, country.lon, this.globeRadius);
      
      // Marker point group
      const markerGroup = new THREE.Group();
      markerGroup.position.copy(position);
      markerGroup.userData = { country: country };

      // Pin core dot
      const pinGeo = new THREE.SphereGeometry(0.08, 16, 16);
      const pinMat = new THREE.MeshBasicMaterial({
        color: 0xff6b35, // Glowing orange indicator
        transparent: true,
        opacity: 0.8
      });
      const pinMesh = new THREE.Mesh(pinGeo, pinMat);
      markerGroup.add(pinMesh);

      // Radar Ring animation
      const ringGeo = new THREE.RingGeometry(0.05, 0.15, 16);
      const ringMat = new THREE.MeshBasicMaterial({
        color: 0xff6b35,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.4
      });
      const radarRing = new THREE.Mesh(ringGeo, ringMat);
      radarRing.name = "radar";
      markerGroup.add(radarRing);
      
      // Orient the marker flat to the sphere surface
      markerGroup.lookAt(new THREE.Vector3(0, 0, 0));
      // Invert orientation since lookAt looks toward center
      markerGroup.rotateY(Math.PI);

      this.globeMesh.add(markerGroup);
      this.markers.push(markerGroup);
    });

    // 6. Raycasting Interactivity
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();
    
    // Add Click listener
    this.canvas.addEventListener("click", (e) => this.onClick(e));
    this.canvas.addEventListener("mousemove", (e) => this.onMouseMove(e));

    this.isThinking = false;
    this.targetRotationY = 0;
    this.targetRotationX = 0;
  }

  latLonToVector3(lat, lon, radius) {
    const phi = (90 - lat) * (Math.PI / 180);
    const theta = (lon + 180) * (Math.PI / 180);

    const x = -(radius * Math.sin(phi) * Math.sin(theta));
    const y = radius * Math.cos(phi);
    const z = radius * Math.sin(phi) * Math.cos(theta);

    return new THREE.Vector3(x, y, z);
  }

  onResize() {
    this.width = this.container.clientWidth;
    this.height = this.container.clientHeight;
    
    this.camera.aspect = this.width / this.height;
    this.camera.updateProjectionMatrix();
    
    this.renderer.setSize(this.width, this.height);
  }

  onMouseMove(e) {
    const rect = this.canvas.getBoundingClientRect();
    this.mouse.x = ((e.clientX - rect.left) / this.width) * 2 - 1;
    this.mouse.y = -((e.clientY - rect.top) / this.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    // Intersect the marker pin meshes
    const pinMeshes = this.markers.map(m => m.children[0]);
    const intersects = this.raycaster.intersectObjects(pinMeshes);

    if (intersects.length > 0) {
      this.canvas.style.cursor = "pointer";
    } else {
      this.canvas.style.cursor = "default";
    }
  }

  onClick(e) {
    const rect = this.canvas.getBoundingClientRect();
    this.mouse.x = ((e.clientX - rect.left) / this.width) * 2 - 1;
    this.mouse.y = -((e.clientY - rect.top) / this.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    
    // Map list of meshes in markers
    const pinMeshes = this.markers.map(m => m.children[0]);
    const intersects = this.raycaster.intersectObjects(pinMeshes);

    if (intersects.length > 0) {
      const clickedPin = intersects[0].object;
      const clickedGroup = clickedPin.parent;
      const countryData = clickedGroup.userData.country;
      
      console.log(`Globe Raycast hit: ${countryData.name}`);
      
      // Visual feedback: briefly spike pin scaling
      clickedGroup.scale.set(1.6, 1.6, 1.6);
      setTimeout(() => clickedGroup.scale.set(1, 1, 1), 300);

      // Smoothly rotate the globe to face the clicked position
      const targetPos = clickedGroup.position.clone().normalize();
      
      // Calculate rotation targets to center this vector on the screen (z-axis)
      this.targetRotationY = Math.atan2(-targetPos.x, targetPos.z);
      this.targetRotationX = Math.asin(targetPos.y);

      // Trigger callback
      if (this.onCountrySelected) {
        this.onCountrySelected(countryData);
      }
    }
  }

  setThinking(status) {
    this.isThinking = status;
  }

  animate() {
    requestAnimationFrame(() => this.animate());

    const delta = this.isThinking ? 0.03 : 0.003;
    
    // Gentle rotation
    if (!this.targetRotationY && !this.targetRotationX) {
      this.globeMesh.rotation.y += delta;
    } else {
      // Lerp toward targeted country clicked rotation
      this.globeMesh.rotation.y += (this.targetRotationY - this.globeMesh.rotation.y) * 0.08;
      this.globeMesh.rotation.x += (this.targetRotationX - this.globeMesh.rotation.x) * 0.08;
      
      // Reset target check to allow passive rotation again if we are close
      if (Math.abs(this.targetRotationY - this.globeMesh.rotation.y) < 0.01) {
        this.targetRotationY = 0;
        this.targetRotationX = 0;
      }
    }

    // Spin outer orbit ring opposite direction
    this.orbitRing.rotation.z -= 0.001;

    // Animate radar rings on markers
    this.markers.forEach(marker => {
      const radar = marker.getObjectByName("radar");
      if (radar) {
        radar.scale.addScalar(0.012);
        radar.material.opacity -= 0.009;
        
        if (radar.scale.x > 2.5) {
          radar.scale.set(0.5, 0.5, 0.5);
          radar.material.opacity = 0.6;
        }
      }
    });

    this.renderer.render(this.scene, this.camera);
  }
}
