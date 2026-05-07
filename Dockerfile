# ============================================================
# PlaceGuard Dockerfile — Multi-stage production build
# ============================================================

# ---- Stage 1: Base dependencies ----
FROM python:3.12-slim AS base

# Security: create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---- Stage 2: Install Python dependencies ----
FROM base AS deps

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e "." && \
    pip install --no-cache-dir \
        pandas \
        pytest \
        pytest-asyncio \
        pytest-cov

# ---- Stage 3: Final image ----
FROM deps AS final

# Copy source
COPY src/ ./src/
COPY tests/ ./tests/

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Environment defaults (override via docker-compose or Railway)
ENV PYTHONPATH=/app/src
ENV API_HOST=0.0.0.0
ENV API_PORT=8000
ENV LOG_LEVEL=INFO

EXPOSE 8000 8501

# Default: run API server
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
