/**
 * JarvisWebSocket Class
 * Handles connection, reconnecting with exponential backoff, message queuing, 
 * and routing incoming socket payloads to relevant callback listeners.
 */
class JarvisWebSocket {
  constructor(url = 'ws://localhost:8000/ws') {
    this.url = url;
    this.socket = null;
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectDelay = 30000; // 30 seconds
    this.listeners = {};
    this.sendQueue = [];
    
    // Auto-connect
    this.connect();
  }

  /**
   * Register callbacks for specific message types
   * @param {string} type - Message type (e.g. 'chat_response')
   * @param {function} callback - Callback function receiving the data payload
   */
  on(type, callback) {
    if (!this.listeners[type]) {
      this.listeners[type] = [];
    }
    this.listeners[type].push(callback);
  }

  /**
   * Connect to the WebSocket server
   */
  connect() {
    console.log(`[WebSocket] Initiating connection to ${this.url}...`);
    this.socket = new WebSocket(this.url);

    this.socket.onopen = () => {
      this.isConnected = true;
      this.reconnectAttempts = 0;
      console.log('[WebSocket] Connection established successfully.');
      
      // Notify application listeners about state change
      this.trigger('socket_open', { message: 'Connection online' });
      
      // Flush send queue
      this.flushQueue();
    };

    this.socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        const type = payload.type;
        const data = payload.data;
        
        console.log(`[WebSocket] Received message type: ${type}`, data);
        
        // Trigger generic packet listener and specific packet listener
        this.trigger(type, data);
        this.trigger('*', { type, data });
      } catch (err) {
        console.error('[WebSocket] Error parsing message payload:', err, event.data);
      }
    };

    this.socket.onerror = (error) => {
      console.error('[WebSocket] Error encountered:', error);
      this.trigger('socket_error', error);
    };

    this.socket.onclose = (event) => {
      this.isConnected = false;
      console.warn(`[WebSocket] Connection closed (code: ${event.code}). Attempting reconnect...`);
      this.trigger('socket_close', event);
      
      this.attemptReconnect();
    };
  }

  /**
   * Reconnect with exponential backoff
   */
  attemptReconnect() {
    this.reconnectAttempts++;
    // Calculate exponential delay: 2^attempts * 1000ms, capped at maxReconnectDelay
    const delay = Math.min(
      Math.pow(2, this.reconnectAttempts - 1) * 1000, 
      this.maxReconnectDelay
    );

    console.log(`[WebSocket] Retrying in ${delay / 1000}s (Attempt ${this.reconnectAttempts})...`);
    
    setTimeout(() => {
      if (!this.isConnected) {
        this.connect();
      }
    }, delay);
  }

  /**
   * Send data to the server, queueing if disconnected
   * @param {string} type - Message type
   * @param {object} data - Payload
   */
  send(type, data = {}) {
    const packet = { type, data };
    
    if (this.isConnected && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(packet));
    } else {
      console.warn(`[WebSocket] Disconnected. Queuing message type: ${type}`);
      this.sendQueue.push(packet);
    }
  }

  /**
   * Flush the message queue
   */
  flushQueue() {
    if (this.sendQueue.length === 0) return;
    
    console.log(`[WebSocket] Flushing ${this.sendQueue.length} queued messages...`);
    while (this.sendQueue.length > 0 && this.isConnected) {
      const packet = this.sendQueue.shift();
      this.socket.send(JSON.stringify(packet));
    }
  }

  /**
   * Trigger registered event callbacks
   */
  trigger(type, data) {
    if (this.listeners[type]) {
      this.listeners[type].forEach(callback => {
        try {
          callback(data);
        } catch (err) {
          console.error(`[WebSocket] Error in listener callback for type '${type}':`, err);
        }
      });
    }
  }
}
