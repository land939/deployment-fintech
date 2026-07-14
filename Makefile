"""Makefile for common development tasks."""

.PHONY: help install dev-install lint format type-check bandit security test pre-commit clean setup-db migrate docker-build docker-up docker-down docker-logs docker-ps docker-shell docker-test

help:
	@echo "GTA Fintech - Available Commands"
	@echo "=================================="
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
	pip install --upgrade pip
	pip install -e .

dev-install:
	pip install --upgrade pip
	pip install -e ".[dev]"
	pre-commit install

lint:
	ruff check config database services routers schemas utils tests

format:
	ruff format config database services routers schemas utils tests
	ruff check --fix config database services routers schemas utils tests

type-check:
	mypy --config-file pyproject.toml

bandit:
	bandit -c .bandit -r config database services routers schemas utils

security: lint bandit
	@echo "✅ Security checks passed"

test:
	pytest tests/ -v --cov=. --cov-report=html

pre-commit:
	pre-commit run --all-files

clean:
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .coverage htmlcov dist build *.egg-info

setup-db:
	python -c "from database import init_db; import asyncio; asyncio.run(init_db())"

migrate:
	alembic upgrade head

run:
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Docker commands
docker-build:
	docker-compose -f docker/docker-compose.yml build

docker-up:
	docker-compose -f docker/docker-compose.yml up -d

docker-down:
	docker-compose -f docker/docker-compose.yml down

docker-ps:
	docker-compose -f docker/docker-compose.yml ps

docker-logs:
	docker-compose -f docker/docker-compose.yml logs -f

docker-logs-api:
	docker-compose -f docker/docker-compose.yml logs -f api

docker-shell:
	docker-compose -f docker/docker-compose.yml exec api bash

docker-test:
	docker-compose -f docker/docker-compose.yml exec api pytest tests/ -v

docker-clean:
	docker-compose -f docker/docker-compose.yml down -v
