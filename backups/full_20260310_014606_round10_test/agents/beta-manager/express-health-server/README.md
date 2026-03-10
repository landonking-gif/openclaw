# Express Health Server

A simple Express.js server with a health check endpoint.

## Setup

1. Install dependencies:
```bash
npm install
```

## Running the Server

Start the server:
```bash
npm start
```

The server will start on port 3000 (or use the `PORT` environment variable).

## Endpoints

### GET /
Welcome message with API information.

### GET /health
Health check endpoint returning:
```json
{
  "status": "ok",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "uptime": 42
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT`   | Server port | 3000    |

## Error Handling

- 404 errors return a JSON response with route not found
- Server errors are caught and logged with stack traces
