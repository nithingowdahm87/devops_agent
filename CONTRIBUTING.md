# Contributing to DevOps Agent

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ".[test]"
```

## Running Tests

```bash
pytest tests/ -v
```

## Code Style

This project uses pre-commit hooks. Install them with:

```bash
pre-commit install
pre-commit run --all-files
```

## Reporting Issues

Please include:
- Python version
- Operating system
- Steps to reproduce
- Full traceback if applicable
