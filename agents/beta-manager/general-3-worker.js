#!/usr/bin/env node
// general-3 worker daemon
const http = require('http');
const PORT = 18813;

const server = http.createServer((req, res) => {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ready', port: PORT, worker: 'general-3' }));
});

server.listen(PORT, () => {
    console.log(`🟢 general-3 worker ready on port ${PORT}`);
});

setInterval(() => {
    console.log(`[${new Date().toISOString()}] general-3 heartbeat`);
}, 60000);
