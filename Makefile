# DevOps Agent Makefile
.PHONY: install test test-unit lint format run run-heal docker-build docker-run clean check tree \
        health dry-run diff type-check coverage integration audit

# Default target
help:
	@echo "DevOps Agent - Available targets:"
	@echo "  install     - Install package and dev dependencies"
	@echo "  test        - Run full test suite"
	@echo "  test-unit   - Run unit tests only"
	@echo "  lint        - Run linters (ruff, mypy)"
	@echo "  format      - Format code with ruff"
	@echo "  run         - Run agent on PROJECT=/path/to/project"
	@echo "  run-heal    - Run agent with healing enabled"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run  - Run agent in Docker"
	@echo "  clean       - Clean build artifacts"
	@echo "  health      - Preflight check all dependencies"
	@echo "  dry-run     - Preview artifacts for sample-node-app without writing"
	@echo "  diff        - Compare latest two runs in .artifacts_history/"
	@echo "  type-check  - Run mypy strict type checking"
	@echo "  coverage    - Run tests with HTML coverage report"
	@echo "  integration - Run integration tests against sample-node-app"
	@echo "  audit       - Show latest audit log"

# Install package with dev dependencies
install:
	pip install -e ".[test]"
	pre-commit install || true

# Run tests
test:
	pytest tests/ -v --tb=short

# Run unit tests only (skip integration)
test-unit:
	pytest tests/ -v --tb=short -k "not integration"

# Run linters
lint:
	ruff check src/ tests/
	mypy src/

# Format code
format:
	ruff check --fix src/ tests/
	ruff format src/ tests/

# Run agent (requires PROJECT variable)
run:
	@if [ -z "$(PROJECT)" ]; then \
		echo "Usage: make run PROJECT=/path/to/project"; \
		exit 1; \
	fi
	python main.py --no-prompts --no-heal $(PROJECT)

# Run agent with healing
run-heal:
	@if [ -z "$(PROJECT)" ]; then \
		echo "Usage: make run-heal PROJECT=/path/to/project"; \
		exit 1; \
	fi
	python main.py --no-prompts $(PROJECT)

# Build Docker image
docker-build:
	docker build -t devops-agent:latest .

# Run in Docker (requires PROJECT variable)
docker-run:
	@if [ -z "$(PROJECT)" ]; then \
		echo "Usage: make docker-run PROJECT=/path/to/project"; \
		exit 1; \
	fi
	docker run --rm -v $(PROJECT):/project devops-agent:latest --no-prompts --no-heal /project

# Clean build artifacts
clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete

# Check for common issues
check:
	@echo "Checking for NVIDIA_API_KEY..."
	@if [ -z "$$NVIDIA_API_KEY" ]; then \
		echo "WARNING: NVIDIA_API_KEY not set in environment"; \
	else \
		echo "NVIDIA_API_KEY is set"; \
	fi
	@echo "Checking configs/prompts exist..."
	@ls configs/prompts/*/*.md >/dev/null && echo "Prompt templates found" || echo "ERROR: Prompt templates missing"

# Show project structure
tree:
	@find . -type f -name "*.py" | grep -v __pycache__ | grep -v venv | sort

## health: Preflight check all dependencies
health:
	python main.py --health

## dry-run: Preview artifacts for sample-node-app without writing
dry-run:
	python main.py --no-prompts --dry-run sample-node-app

## diff: Compare latest two runs in .artifacts_history/
diff:
	@runs=$$(ls -t .artifacts_history/ 2>/dev/null | head -2); \
	 count=$$(echo "$$runs" | wc -w); \
	 if [ "$$count" -lt 2 ]; then echo "Need at least 2 runs to diff."; exit 1; fi; \
	 new=$$(echo $$runs | cut -d' ' -f1); \
	 old=$$(echo $$runs | cut -d' ' -f2); \
	 echo "Diffing $$old → $$new"; \
	 diff -r .artifacts_history/$$old .artifacts_history/$$new --color=always || true

## type-check: Run mypy strict type checking
type-check:
	mypy src/ --config-file pyproject.toml

## coverage: Run tests with HTML + terminal coverage report
coverage:
	pytest tests/ --cov=src --cov-report=html --cov-report=term-missing
	@echo "HTML report: htmlcov/index.html"

## integration: Run integration tests against sample-node-app
integration:
	pytest tests/test_integration_sample_node_app.py -v

## audit: Show latest audit log
audit:
	@ls -lt audit_logs/*.json 2>/dev/null | head -10 || echo "No audit logs yet."
	@echo "---"
	@cat $$(ls -t audit_logs/*.json 2>/dev/null | head -1) 2>/dev/null || true