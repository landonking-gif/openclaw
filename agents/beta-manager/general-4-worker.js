#!/usr/bin/env node
// general-4 worker daemon
const http = require('http');
const PORT = 18814;

const server = http.createServer((req, res) => {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ready', port: PORT, worker: 'general-4' }));
});

server.listen(PORT, () => {
    console.log(`🟢 general-4 worker ready on port ${PORT}`);
});

setInterval(() => {
    console.log(`[${new Date().toISOString()}] general-4 heartbeat`);
}, 60000);
