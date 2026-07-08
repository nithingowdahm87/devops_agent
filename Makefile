# DevOps Agent Makefile
.PHONY: install test lint run clean help

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