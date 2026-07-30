# Stage de base minimal, commun aux deux stages suivants
FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Seulement les outils nécessaires À L'EXÉCUTION (pas de compilateur ici)
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*


# Stage de build : ajoute les outils de compilation UNIQUEMENT ici
FROM base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libc6-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml ./
COPY config ./config
COPY database ./database
COPY services ./services
COPY routers ./routers
COPY schemas ./schemas
COPY utils ./utils
COPY main.py .

RUN pip install --upgrade pip setuptools wheel && \
    pip install -e .


# Stage final : hérite de "base" (sans gcc/build-essential)
FROM base

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml .
COPY config ./config
COPY database ./database
COPY services ./services
COPY routers ./routers
COPY schemas ./schemas
COPY utils ./utils
COPY migrations ./migrations
COPY models ./models
COPY templates ./templates
COPY static ./static
COPY abi ./abi
COPY main.py .

RUN mkdir -p logs models && \
    chmod -R 755 logs models

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]