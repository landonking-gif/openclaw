#!/usr/bin/env node
// general-2 worker daemon
const http = require('http');
const PORT = 18812;

const server = http.createServer((req, res) => {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ready', port: PORT, worker: 'general-2' }));
});

server.listen(PORT, () => {
    console.log(`🟢 general-2 worker ready on port ${PORT}`);
});

setInterval(() => {
    console.log(`[${new Date().toISOString()}] general-2 heartbeat`);
}, 60000);
