# 🚀 DevOps Agent — AI-Powered Infrastructure Generation CLI

![Project Status](https://img.shields.io/badge/status-stable-green)
![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)
![NVIDIA Only](https://img.shields.io/badge/LLM-NVIDIA%20Only-purple.svg)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)
![License MIT](https://img.shields.io/badge/license-MIT-yellow.svg)

**CLI-only DevOps tool that generates production-grade infrastructure (Docker, Kubernetes, CI/CD) from any codebase using NVIDIA LLM — with policy validation, local artifact generation, and secure file handling.**

## Table of Contents

- [🏗️ Architecture](#️-architecture)
- [✨ Features](#-features)
- [🚀 Quick Start](#-quick-start)
- [📦 Installation](#-installation)
- [⚙️ Configuration](#️-configuration)
- [🧪 Testing](#-testing)
- [☸️ Deployment](#️-deployment)
- [📁 Project Structure](#-project-structure)
- [📝 Documentation](#-documentation)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI Entry Point                          │
│                         main.py                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      V2 Orchestrator                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Planner   │──│  Generator  │──│  Evaluator  │             │
│  │ (Architecture│  │  (NVIDIA    │  │ (Linters +  │             │
│  │  Planner)   │  │   LLM)      │  │   Heuristics)            │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│         │               │               │                        │
│         ▼               ▼               ▼                        │
│  ┌─────────────────────────────────────────────┐               │
│  │           Validator / Healer                │               │
│  │   hadolint │ kubeconform │ trivy │ checkov  │               │
│  └─────────────────────────────────────────────┘               │
│         │               │               │                        │
│         ▼               ▼               ▼                        │
│  ┌─────────────────────────────────────────────┐               │
│  │          Artifact Manager                   │               │
│  │   Write Gate + Quarantine + Idempotency     │               │
│  └─────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

**Key Design Principles:**
- **Single Provider**: NVIDIA LLM only — no multi-provider routing complexity
- **CLI-Only**: No server/API mode — runs as a local tool
- **Local Writes Only**: No GitOps PR publishing — outputs go to `outputs/` directory
- **Fail-Fast**: Missing NVIDIA credentials = immediate error, no mock fallback
- **Security First**: Sandboxed prompt rendering, path validation, no shell execution

## ✨ Features

### Core Generation
- 🔍 **Code Analysis** — Detects language, framework, database stack (Postgres, Redis, MongoDB, etc.) from any project
- 🐳 **Docker Generation** — Production-grade multi-stage Dockerfiles with non-root user, health checks, OCI labels
- ☸️ **Kubernetes Manifests** — Full K8s resources: Deployment, Service, HPA, PDB, NetworkPolicy, Namespace
- 🔁 **CI/CD Pipelines** — Generated GitHub Actions workflows with matrix strategy, security scanning, SARIF upload

### Validation & Quality
- 🛡️ **Policy Engine** — Environment-aware validation (prod vs dev rules)
- 🔧 **Auto-Healer** — LLM-based fix loop for validation failures
- 📏 **Linter Integration** — Real `hadolint`, `kubeconform`, `yamllint`, `trivy`, `checkov` via subprocess
- ⚖️ **Hybrid Scoring** — Linter scores (50%) + Heuristics (30%) + LLM Judge (20%, optional)
- 🔒 **Idempotency** — Deterministic YAML/Dockerfile/JSON output normalization

### Security & Safety
- 🚫 **No Shell Execution** — Removed arbitrary command execution capability
- 🛡️ **Prompt Injection Defense** — Jinja2 sandboxed template rendering with allowlisted variables
- 📁 **Path Traversal Protection** — All file writes validated against project root
- 🗂️ **Quarantine System** — Failed artifacts isolated in `.artifacts_history/` with metadata
- ⚡ **Fail-Fast Config** — Missing NVIDIA_API_KEY = immediate error, no silent mock fallback

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+** (Docker image targets 3.12)
- **NVIDIA API Key** — Get one at https://build.nvidia.com
- **Docker** (optional, for containerised runs)

### Local Install
```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ".[test]"
```

### Configure NVIDIA API Key
```bash
cp .env.example .env
# Edit .env and add your NVIDIA_API_KEY
```

### Generate Infrastructure
```bash
# Auto-pilot mode (no prompts, no heal)
python main.py --no-prompts --no-heal /path/to/project

# With healing enabled (default)
python main.py --no-prompts /path/to/project

# Target specific service in monorepo
python main.py --no-prompts --service backend /path/to/project
```

Outputs are written to:
- `outputs/per-service/<service>/` — Dockerfile, K8s manifests, CI workflows
- `outputs/shared/` — docker-compose.yml, shared configs

## 📦 Installation

### Local Development
```bash
git clone https://github.com/nithingowdahm87/devops_agent
cd devops_agent
python3 -m venv venv
source venv/bin/activate
pip install -e ".[test]"
```

### Docker
```bash
docker build -t devops-agent .
# Run against a project directory
docker run -v /path/to/project:/project devops-agent --no-prompts --no-heal /project
```

### Makefile (Convenience)
```bash
make install       # Install dev dependencies
make test          # Run test suite
make lint          # Run linters
make run PROJECT=/path/to/project  # Run agent
```

## ⚙️ Configuration

All settings via environment variables or `.env` file (auto-loaded from project root).

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `NVIDIA_API_KEY` | **Yes** | — | NVIDIA NIM API key (get from build.nvidia.com) |
| `NVIDIA_MODEL` | No | `meta/llama-3.1-405b-instruct` | NVIDIA model to use |
| `LLM_TEMPERATURE` | No | `0.1` | Generation temperature (0.0-1.0) |
| `LLM_MAX_TOKENS` | No | `8192` | Max tokens per request |
| `LLM_TIMEOUT_SECONDS` | No | `180` | Request timeout |
| `LLM_MAX_RETRIES` | No | No | `3` | Max retry attempts |
| `LOG_JSON` | No | `false` | Structured JSON logging |
| `ENVIRONMENT` | No | `dev` | `dev` or `prod` (affects policy strictness) |

## 🧪 Testing

```bash
# Run full test suite
pytest tests/ -v --tb=short

# Run specific test categories
pytest tests/test_policy.py -v
pytest tests/test_v2_modules.py -v
pytest tests/test_idempotency.py -v
```

The test suite covers:
- **Core Logic** — `test_v2_modules.py`, `test_schemas.py`, `test_clean_markdown.py`
- **Validation** — `test_idempotency.py`, `test_write_gate.py`, `test_policy.py`, `test_policy_engine.py`
- **Safety** — `test_tools_file_ops.py` (path traversal), `test_sanitizer.py` (prompt injection)
- **Engine** — `test_ooda_healer.py`, `test_memory.py`, `test_integrity_audit.py`

## ☸️ Deployment

### Docker Image
```bash
docker build -t devops-agent .
docker run -v /host/project:/project devops-agent --no-prompts /project
```

### Kubernetes (Job/CronJob)
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: devops-agent
spec:
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: agent
            image: devops-agent:latest
            args: ["--no-prompts", "--no-heal", "/project"]
            volumeMounts:
            - name: project
              mountPath: /project
          volumes:
          - name: project
            persistentVolumeClaim:
              claimName: project-pvc
          restartPolicy: OnFailure
```

## 📁 Project Structure

```
devops_agent/
├── main.py                       # CLI entry point
├── Makefile                      # Convenience targets
├── pyproject.toml                # Project metadata & deps
├── requirements.txt              # Pinned dependencies
├── Dockerfile                    # Multi-stage CLI image
├── .env.example                  # Configuration template
├── configs/
│   └── prompts/                  # Jinja2 prompt templates
│       ├── docker/
│       │   ├── docker_production.md
│       │   └── docker_compose.md
│       ├── k8s/
│       │   └── k8s_production.md
│       └── cicd/
│           └── github_actions.md
├── src/
│   ├── entrypoints/
│   │   └── cli_main.py           # CLI pipeline runner
│   ├── decision_engine/
│   │   ├── orchestrator.py       # V2 Orchestrator (single path)
│   │   ├── planner/              # Architecture planning
│   │   ├── generator/            # LLM generation
│   │   ├── scoring/              # Hybrid evaluation
│   │   └── repair/               # Healer
│   ├── engine/
│   │   ├── llm.py                # NVIDIA-only LLM caller
│   │   ├── validate.py           # Linter integrations
│   │   ├── heal.py               # Healer
│   │   ├── artifact_manager.py   # Write gate + quarantine
│   │   ├── idempotency.py        # Output normalization
│   │   ├── policy_engine.py      # Policy validation
│   │   ├── severity.py           # Severity levels
│   │   └── secrets_manifest.py   # Secrets documentation
│   ├── llm_clients/
│   │   ├── nvidia_client.py      # NVIDIA wrapper
│   │   └── mock_client.py        # Test-only mock
│   ├── agents/
│   │   └── code_analysis_agent.py # Project analysis
│   ├── tools/
│   │   └── file_ops.py           # Safe file operations
│   ├── utils/
│   │   ├── prompt_loader.py      # Jinja2 sandboxed renderer
│   │   └── secrets.py            # Secrets loading
│   └── schemas.py                # Pydantic models
├── tests/                        # pytest suite
├── sample-node-app/              # Demo project
└── docs/                         # Documentation
```

## 📝 Documentation

- [Architecture](docs/architecture.md)
- [User Guide](docs/user-guide.md)
- [Deployment Guide](docs/deploy.md)

## 🤝 Contributing

We welcome contributions — bug fixes, new prompt templates, additional linter integrations, and infra generation patterns.

1. Fork the repo
2. Create a feature branch
3. Install dev extras: `pip install -e ".[test]"`
4. Run `pre-commit install` (then `pre-commit run --all-files`)
5. Add tests for any new behaviour
6. Open a PR

## 📄 License

Released under the [MIT License](LICENSE).