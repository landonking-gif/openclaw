# Use Python 3.11 slim image for minimal size with full Python compatibility
# Slim variant removes unnecessary build tools while keeping runtime essentials
FROM python:3.11-slim

# Set working directory early for all subsequent operations
WORKDIR /app

# Create a non-root user for security
# -r: system group/user (no login required)
# --no-create-home: Don't create a home directory (smaller image)
# --uid 1000: Consistent UID across builds for volume permissions
RUN groupadd -r appgroup && useradd -r -g appgroup --uid 1000 appuser

# Install system dependencies first (for layer caching)
# These are needed for compiling any binary Python packages
# Clean up apt cache in the same RUN layer to reduce image size
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements.txt first for better layer caching
# Dependencies change less frequently than code, so this layer is cached
COPY requirements.txt .

# Install Python dependencies
# --no-cache-dir: Don't cache pip packages (reduces image size by ~50MB)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code after dependencies (smaller layer when code changes)
COPY main.py .

# Change ownership to non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user for security
# Container runs without privileged access, limiting potential damage
USER appuser

# Expose port 8000 for the FastAPI application
EXPOSE 8000

# Use exec form of CMD for proper signal handling (allows graceful shutdown)
# --host 0.0.0.0: Bind to all interfaces (required for container networking)
# --port 8000: Match the exposed port
# main:app: Import 'app' from 'main.py' module (FastAPI convention)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
