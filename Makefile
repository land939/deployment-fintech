"""Makefile for common development tasks."""

.PHONY: help install dev-install lint format type-check bandit security test pre-commit clean setup-db migrate

help:
	@echo "GTA Fintech - Available Commands"
	@echo "=================================="
	@echo "make install        - Install dependencies"
	@echo "make dev-install    - Install with dev dependencies"
	@echo "make lint           - Run ruff linter"
	@echo "make format         - Format code with ruff"
	@echo "make type-check     - Run mypy type checking"
	@echo "make bandit         - Run security scan with bandit"
	@echo "make security       - Run all security checks"
	@echo "make test           - Run pytest suite"
	@echo "make pre-commit     - Run all pre-commit hooks"
	@echo "make clean          - Clean build artifacts"
	@echo "make setup-db       - Initialize database"
	@echo "make run            - Start FastAPI server"

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
