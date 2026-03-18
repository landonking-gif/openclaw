const express = require('express');
const app = express();
const PORT = 18805;

// Middleware for parsing JSON
app.use(express.json());

// Health check endpoint - must be BEFORE wildcard/error handlers
app.get('/health', (req, res) => {
    res.json({
        status: 'ok',
        service: 'coding-3',
        port: 18805,
        timestamp: Date.now()
    });
});

// Welcome endpoint
app.get('/', (req, res) => {
    res.json({
        message: 'coding-3 agent',
        service: 'coding-3',
        port: 18805
    });
});

// 404 handler for unknown routes (wildcard - must be LAST among specific routes)
app.use((req, res) => {
    res.status(404).json({
        error: 'Not Found',
        message: `Cannot ${req.method} ${req.path}`
    });
});

// Global error handler (must be LAST)
app.use((err, req, res, next) => {
    console.error('Error:', err.stack);
    res.status(err.status || 500).json({
        error: err.name || 'Internal Server Error',
        message: err.message || 'Something went wrong!'
    });
});

// Start server
app.listen(PORT, () => {
    console.log(`coding-3 server running on port ${PORT}`);
    console.log(`Health endpoint: http://localhost:${PORT}/health`);
});
