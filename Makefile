.PHONY: help install dev-install lint format type-check bandit security test pre-commit clean setup-db migrate run smoke docker-build docker-up docker-down docker-logs docker-ps docker-shell docker-test

# Prefer project venv when present so `make` works without `source venv/bin/activate`
PYTHON ?= $(shell if [ -x venv/bin/python ]; then echo venv/bin/python; else echo python3; fi)
PIP = $(PYTHON) -m pip
DOCKER_COMPOSE = docker compose -f docker/docker-compose.yml

help:
	@echo "GTA Fintech - Available Commands"
	@echo "=================================="
	@echo ""
	@echo "Using PYTHON=$(PYTHON)"
	@echo ""
	@echo "📦 Installation:"
	@echo "  make install        - Install dependencies"
	@echo "  make dev-install    - Install with dev dependencies"
	@echo ""
	@echo "🔍 Code Quality:"
	@echo "  make lint           - Run ruff linter"
	@echo "  make format         - Format code with ruff"
	@echo "  make type-check     - Run mypy type checking"
	@echo "  make bandit         - Run security scan with bandit"
	@echo "  make security       - Run all security checks"
	@echo "  make pre-commit     - Run all pre-commit hooks"
	@echo ""
	@echo "🧪 Testing:"
	@echo "  make test           - Run pytest suite"
	@echo ""
	@echo "🗄️  Database:"
	@echo "  make setup-db       - Initialize database"
	@echo "  make migrate        - Run database migrations"
	@echo ""
	@echo "🚀 Development:"
	@echo "  make run            - Start FastAPI server locally"
	@echo "  make clean          - Clean build artifacts"
	@echo ""
	@echo "🐳 Docker:"
	@echo "  make docker-build   - Build Docker image"
	@echo "  make docker-up      - Start Docker containers"
	@echo "  make docker-down    - Stop Docker containers"
	@echo "  make docker-ps      - Show running containers"
	@echo "  make docker-logs    - View Docker logs"
	@echo "  make docker-shell   - Open shell in API container"
	@echo "  make docker-test    - Run tests in Docker"

install:
	$(PIP) install --upgrade pip
	$(PIP) install -e .

dev-install:
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	$(PYTHON) -m pre_commit install

lint:
	$(PYTHON) -m ruff check config database services routers schemas utils tests main.py

format:
	$(PYTHON) -m ruff format config database services routers schemas utils tests main.py
	$(PYTHON) -m ruff check --fix config database services routers schemas utils tests main.py

type-check:
	$(PYTHON) -m mypy --config-file pyproject.toml

bandit:
	$(PYTHON) -m bandit -c .bandit -r config database services routers schemas utils

security: lint bandit
	@echo "✅ Security checks passed"

test:
	$(PYTHON) -m pytest tests/ -v --cov=. --cov-report=html

pre-commit:
	$(PYTHON) -m pre_commit run --all-files

clean:
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .coverage htmlcov dist build *.egg-info

setup-db:
	$(PYTHON) -c "from database import init_db; import asyncio; asyncio.run(init_db())"

migrate:
	$(PYTHON) -m alembic upgrade head

# Port 8000 is often taken (e.g. Infisical). Override: make run PORT=9000
PORT ?= 8765

run:
	@if ss -H -tln 2>/dev/null | grep -qE ":$(PORT)\\b"; then \
		echo "Port $(PORT) déjà utilisé. Essayez: make run PORT=8766"; exit 1; \
	fi
	$(PYTHON) -m uvicorn main:app --reload --host 127.0.0.1 --port $(PORT)

smoke:
	@echo "Smoke contre http://127.0.0.1:$(PORT) (serveur déjà lancé requis)"
	curl -sf "http://127.0.0.1:$(PORT)/health" | $(PYTHON) -m json.tool
	curl -sf -o /dev/null -w "GET / -> %{http_code}\n" "http://127.0.0.1:$(PORT)/"
	curl -sf -o /dev/null -w "GET /static/app.css -> %{http_code}\n" "http://127.0.0.1:$(PORT)/static/app.css"
	curl -sf -X POST "http://127.0.0.1:$(PORT)/fraud/check" \
		-H 'Content-Type: application/json' -d '{"amount":100,"hour":14}' | $(PYTHON) -m json.tool

# Docker Compose v2 plugin (`docker compose`, not legacy `docker-compose`)
docker-build:
	$(DOCKER_COMPOSE) build

docker-up:
	$(DOCKER_COMPOSE) up -d

docker-down:
	$(DOCKER_COMPOSE) down

docker-ps:
	$(DOCKER_COMPOSE) ps

docker-logs:
	$(DOCKER_COMPOSE) logs -f

docker-logs-api:
	$(DOCKER_COMPOSE) logs -f api

docker-shell:
	$(DOCKER_COMPOSE) exec api bash

docker-test:
	$(DOCKER_COMPOSE) exec api python -m pytest tests/ -v

docker-clean:
	$(DOCKER_COMPOSE) down -v
