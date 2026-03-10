
- Works with any HTTP server
- Works through standard load balancers
- Highest latency due to HTTP overhead per message

---

## 5. Security Considerations

### 5.1 WebSocket Security

**Encryption:**
```javascript
// Always use WSS (WebSocket Secure)
const ws = new WebSocket('wss://example.com/socket');  // ✅
const ws = new WebSocket('ws://example.com/socket');   // ❌ Never in production
```

**Threats:**
- **Cross-Site WebSocket Hijacking (CSWSH):** Attackers on other sites connect via predictable WebSocket URLs
  - Mitigation: Validate `Origin` header during handshake
  
- **Denial of Service:** Attackers open many connections
  - Mitigation: Rate limiting, connection limits per IP

- **Message Injection:** Malformed frames
  - Mitigation: Input validation, frame size limits

**Implementation:**
```javascript
const wss = new WebSocket.Server({ port: 8080 });

wss.on('connection', (ws, req) => {
  // Validate origin
  const origin = req.headers.origin;
  const allowedOrigins = ['https://example.com', 'https://app.example.com'];
  if (!allowedOrigins.includes(origin)) {
    ws.close(1008, 'Invalid origin');
    return;
  }
  
  // Rate limiting (per IP)
  const clientIp = req.socket.remoteAddress;
  if (isRateLimited(clientIp)) {
    ws.close(1008, 'Rate limit exceeded');
    return;
  }
});
```

### 5.2 SSE Security

**CORS Support:**
```javascript
// CORS headers required for cross-origin
res.writeHead(200, {
  'Content-Type': 'text/event-stream',
  'Access-Control-Allow-Origin': '*',  // Or specific domain
  'Access-Control-Allow-Headers': 'Last-Event-ID',
  'X-Content-Type-Options': 'nosniff'
});

// For withCredentials (requires explicit origin)
res.writeHead(200, {
  'Access-Control-Allow-Origin': 'https://client.example.com',
  'Access-Control-Allow-Credentials': 'true'  // Required for cookies
});
```

**Credential Passing:**
```javascript
// Include cookies/auth
const evtSource = new EventSource('/events', {
  withCredentials: true  // Sends cookies, needs explicit origin
});
```

**Threats:**
- **Event Injection:** Server-side XSS via event data
  - Prepare: Always sanitize event data before sending

- **DoS via Connection Exhaustion:** 6-connection limit per domain
  - Prepare: HTTP/2, request Origin validation

### 5.3 Long Polling Security

**Advantage:** Uses standard HTTP security (same as normal API requests)

**CSRF Protection:**
```javascript
// Include CSRF token
app.get('/poll', (req, res) => {
  // Validate CSRF token
  if (!verifyCSRF(req.headers['x-csrf-token'])) {
    return res.status(403).end();
  }
  // ...
});
```

---

## 6. Decision Matrix

### 6.1 Choose WebSocket When:

✅ Real-time bi-directional communication needed  
✅ Chat, multiplayer games, collaborative editing  
✅ High-frequency updates (10+ messages/second)  
✅ Low latency is critical  
✅ Modern browser support only required  
✅ Own both client and server  

### 6.2 Choose SSE When:

✅ Only server needs to push data  
✅ News feeds, stock tickers, notifications  
✅ Simple "server→client" update model  
✅ Want automatic reconnection  
✅ HTTP/2 available (solve 6-connection limit)  
✅ Reusing existing HTTP infrastructure  

### 6.3 Choose Long Polling When:

✅ Must support legacy browsers (IE<=9)  
✅ Corporate proxies/firewalls block WebSocket  
✅ Using existing HTTP infrastructure  
✅ Infrequent updates acceptable  
✅ Development simplicity prioritized over performance  

---

## 7. Implementation Examples

### 7.1 Chat Application

**WebSocket (chosen for real-time bidirectional):**
```javascript
// Client
const ws = new WebSocket('wss://chat.example.com');
ws.onopen = () => {
  ws.send(JSON.stringify({action: 'join', room: 'general'}));
};
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === 'chat') addMessage(msg);
  if (msg.type === 'typing') showTyping(msg.user);
};

// Send message
function sendMessage(text) {
  ws.send(JSON.stringify({type: 'chat', text, room: currentRoom}));
}
```

### 7.2 Stock Ticker

**SSE (chosen for server-push only):**
```javascript
// Client
const evtSource = new EventSource('/stocks/stream');
evtSource.addEventListener('price-update', (e) => {
  const update = JSON.parse(e.data);
  updatePrice(update.symbol, update.price);
});

// Auto-reconnect on error
evtSource.onerror = () => {
  // Browser handles reconnection with Last-Event-ID
};
```

### 7.3 Legacy System

**Long Polling (chosen for compatibility):**
```javascript
// Client
function poll() {
  fetch('/updates')
    .then(r => r.json())
    .then(data => {
      if (data) updateUI(data);
      poll(); // Immediately poll again
    })
    .catch(() => setTimeout(poll, 5000)); // Error: retry with delay
}
poll();
```

---

## 8. Migration Paths

### 8.1 Long Polling → SSE

**Incremental migration:**
```javascript
// Feature detection
if (typeof EventSource !== 'undefined') {
  // Use SSE
  const evtSource = new EventSource('/events');
} else {
  // Fallback to long polling
  poll();
}
```

### 8.2 Long Polling → WebSocket

**With fallback:**
```javascript
function connect() {
  if ('WebSocket' in window) {
    return new WebSocket('wss://...');
  }
  // Fallback to long polling
  return new LongPollingConnection('/poll');
}
```

---

## Source URLs

### Specifications
**Source:** https://datatracker.ietf.org/doc/html/rfc6455 (WebSocket RFC)  
**Source:** https://html.spec.whatwg.org/multipage/comms.html#the-eventsource-interface (EventSource)  
**Source:** https://xhr.spec.whatwg.org/ (XMLHttpRequest - Long Polling)  

### Documentation
**Source:** https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API  
**Source:** https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events  
**Source:** https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events  

### Engineering Articles
**Source:** https://ably.com/topic/polling-vs-websockets  
**Source:** https://ably.com/topic/websocket-vs-sse  
**Source:** https://developer.chrome.com/docs/capabilities/web-apis/websocketstream (Streaming API)  

---

## Research Notes

### Key Findings:

1. **HTTP/2 is critical for SSE:** The 6-connection limit per domain makes SSE problematic in HTTP/1.1 without HTTP/2.

2. **WebSocket backpressure requires WebSocketStream API:** The new APIs (Chrome-only) address the back-pressure problem in traditional `onmessage` handlers.

3. **IE11 is the only reason to use Long Polling:** Modern browsers support WebSocket and SSE; Long Polling is primarily for legacy support.

4. **Auto-reconnect is SSE's killer feature:** Unlike WebSocket where you implement reconnection manually, SSE has built-in reconnection with Last-Event-ID for resume.

5. **Production WebSocket requires sticky sessions:** Without sticky sessions, clients reconnect to a different server without state during horizontal scaling.