.PHONY: help install install-dev test test-cov lint format clean build release docker-build docker-run

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install the package in development mode
	pip install -e .

install-dev: ## Install the package with development dependencies
	pip install -e ".[dev]"

test: ## Run tests
	pytest

test-cov: ## Run tests with coverage
	pytest --cov=src --cov-report=html --cov-report=term-missing

lint: ## Run linting tools
	pylint src/ tests/
	black --check src/ tests/
	isort --check-only src/ tests/
	# mypy src/

format: ## Format code
	black src/ tests/
	isort src/ tests/

clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

build: ## Build the package
	python -m build

release: ## Create a new release
	./release.sh

docker-build: ## Build Docker image
	docker build -t project-manager .

docker-run: ## Run Docker container
	docker run -it --rm project-manager

setup-hooks: ## Install git hooks
	./hooks/install_hooks.sh

check-all: format lint test ## Run all checks (format, lint, test) 