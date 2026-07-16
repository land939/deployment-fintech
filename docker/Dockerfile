# Multi-stage build for production optimization
FROM python:3.12-slim AS base

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*


# Builder stage for dependencies
FROM base AS builder

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements + packages (needed for editable install / setuptools discovery)
COPY pyproject.toml ./
COPY config ./config
COPY database ./database
COPY services ./services
COPY routers ./routers
COPY schemas ./schemas
COPY utils ./utils
COPY main.py .

# Install dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install -e .


# Final stage
FROM base

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY pyproject.toml .
COPY config ./config
COPY database ./database
COPY services ./services
COPY routers ./routers
COPY schemas ./schemas
COPY utils ./utils
COPY migrations ./migrations
COPY models ./models
COPY main.py .

# Create necessary directories
RUN mkdir -p logs models && \
    chmod -R 755 logs models

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Start application with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
