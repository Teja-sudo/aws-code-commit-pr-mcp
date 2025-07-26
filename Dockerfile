# AWS PR Review MCP Server Docker Image
FROM python:3.11-slim

# Set metadata
LABEL maintainer="Enterprise Security Team <security@company.com>"
LABEL description="AWS PR Review MCP Server - Enterprise security analysis for pull requests"
LABEL version="1.0.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Create non-root user for security
RUN groupadd -r mcpuser && useradd -r -g mcpuser mcpuser

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/reports /app/config && \
    chown -R mcpuser:mcpuser /app

# Copy configuration files
COPY config/ /app/config/
COPY .env.example /app/.env.example

# Set proper permissions
RUN chmod +x server.py && \
    chown -R mcpuser:mcpuser /app

# Switch to non-root user
USER mcpuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import boto3; print('AWS SDK available')" || exit 1

# Expose port (if running as HTTP server in future)
EXPOSE 8080

# Default command
CMD ["python", "server.py"]