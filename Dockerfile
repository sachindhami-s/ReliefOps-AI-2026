# =============================================================================
# ReliefOps AI - Production Dockerfile
# Course: CSE476 - Agentic AI and Intelligent Automation
# =============================================================================

FROM python:3.12-slim

# Metadata
LABEL maintainer="ReliefOps AI Development Team" \
      description="Autonomous Multi-Agent Disaster Relief Resource Allocation Platform" \
      version="1.0.0"

# Configure Python & ReliefOps runtime environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    RELIEFOPS_EXECUTION_MODE=deterministic \
    RELIEFOPS_LOG_LEVEL=INFO \
    DATABASE_PATH=/app/data/reliefops.db \
    CHROMADB_PATH=/app/data/chromadb \
    SOP_DIR=/app/data/sops \
    GINI_THRESHOLD=0.35 \
    SURVIVAL_FLOOR_RATIO=0.30 \
    ROUTING_MODE=HAVERSINE_FALLBACK \
    OSRM_BASE_URL=https://router.project-osrm.org \
    ROUTING_TIMEOUT_SECONDS=5.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true

# Install required system dependencies (including libgomp1 for ONNX Runtime / ChromaDB)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgomp1 \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Set application working directory
WORKDIR /app

# Create non-root user and persistent directory structure early
RUN groupadd -g 1000 reliefops && \
    useradd -m -u 1000 -g reliefops reliefops && \
    mkdir -p /app/data /app/data/chromadb /app/data/sops /app/logs && \
    chown -R reliefops:reliefops /app

# Install Python dependencies in a dedicated cached layer
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code (filtered via .dockerignore; excludes .venv, .env, local DBs & backups)
COPY --chown=reliefops:reliefops . .

# Normalize entrypoint line endings (Windows CRLF -> Unix LF) and set permissions
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh && \
    chmod +x /app/docker-entrypoint.sh /app/docker_entrypoint.py && \
    chown -R reliefops:reliefops /app

# Switch to unprivileged non-root application user
USER reliefops

# Expose Streamlit default port
EXPOSE 8501

# Container healthcheck probing Streamlit's internal health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Non-destructive entrypoint verifies existing DB/ChromaDB before starting Streamlit
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
