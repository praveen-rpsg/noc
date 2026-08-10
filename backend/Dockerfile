# ATECH NOC Commander - Backend Dockerfile
# Multi-stage build for optimized production image

# Stage 1: Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc libffi-dev libssl-dev && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ || true

# Stage 2: Production stage
FROM python:3.11-slim as production

WORKDIR /app

# Install runtime dependencies including network tools for discovery
RUN apt-get update && apt-get install -y --no-install-recommends libffi8 libssl3 curl iputils-ping iputils-arping net-tools iproute2 snmp nmap traceroute dnsutils openssh-client telnet && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY server.py .
COPY agents.py .
COPY network_services.py .
COPY device_monitor.py .
COPY upgrade_manager.py .
COPY shared.py .
COPY dbvar.env .
COPY snmp_receiver.py .
COPY cmdb_router.py .
COPY cmdb_manager.py .

# For network discovery, we need to run as root to use raw sockets
# Security note: In production, consider using capabilities instead
# USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV HOST=0.0.0.0
ENV PORT=8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/api/health || exit 1

# Expose port
EXPOSE 8001

# Start application
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
