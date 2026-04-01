const express = require('express');
const app = express();
const PORT = process.env.PORT || 3000;

// Track server start time for uptime calculation
const startTime = Date.now();

// Middleware for parsing JSON
app.use(express.json());

// Welcome endpoint
app.get('/', (req, res) => {
  res.json({
    message: 'Welcome to Express Health Server!',
    version: '1.0.0',
    endpoints: {
      health: '/health'
    }
  });
});

// Health check endpoint
app.get('/health', (req, res) => {
  const uptimeSeconds = Math.floor((Date.now() - startTime) / 1000);
  
  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    uptime: uptimeSeconds
  });
});

// 404 handler for unknown routes
app.use((req, res) => {
  res.status(404).json({
    error: 'Not Found',
    message: `Cannot ${req.method} ${req.path}`,
    timestamp: new Date().toISOString()
  });
});

// Global error handler
app.use((err, req, res, next) => {
  console.error('Error:', err.stack);
  res.status(err.status || 500).json({
    error: err.name || 'Internal Server Error',
    message: err.message || 'Something went wrong!',
    timestamp: new Date().toISOString()
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
  console.log(`Health endpoint: http://localhost:${PORT}/health`);
});
