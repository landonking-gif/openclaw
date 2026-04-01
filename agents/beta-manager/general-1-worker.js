#!/usr/bin/env node
// general-1 worker daemon
const { execSync } = require('child_process');
const http = require('http');

const PORT = 18811;

// Health check server
const server = http.createServer((req, res) => {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ready', port: PORT, worker: 'general-1' }));
});

server.listen(PORT, () => {
    console.log(`🟢 general-1 worker ready on port ${PORT}`);
});

// Keep alive
setInterval(() => {
    console.log(`[${new Date().toISOString()}] general-1 heartbeat`);
}, 60000);
