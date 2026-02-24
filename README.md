# DevOps Agent V14.0

Production-grade AI agent that compiles Dockerfiles, Kubernetes manifests, and CI/CD pipelines from raw codebases. Deterministic compiler architecture with a 6-provider LLM fallback loop. Built to the standard of a 10-year Senior DevSecOps engineer.

---

## Architecture

Codebase Input
│
▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 1 — Code Discovery & Architecture Graph │
│ Detects runtime, frameworks, DB signatures, port, secrets │
└────────────────────────┬────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 2 — LLM Router (6-provider fallback loop) │
│ Groq → Gemini → Cerebras → NVIDIA → OpenRouter → HuggingFace │
└────────────────────────┬────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 3 — Artifact Generation (Dockerfile / K8s / CI/CD) │
│ JSON Schema validation before semantic checks │
└────────────────────────┬────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 4 — OODA Healing Loop │
│ hadolint / kubeconform → Healer → re-validate │
└────────────────────────┬────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 5 — Policy Engine (prod vs dev) │
│ Enforces non-root, resource limits, probe definitions │
└────────────────────────┬────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 6 — Cross-Artifact Integrity Audit │
│ Detects Port Drift, Image Tag Drift, Variable Inconsistency│
└─────────────────────────────────────────────────────────────┘

---

## LLM Providers

The agent uses a **fallback loop** — if the primary provider fails or times out, it automatically tries the next in order. Set `LLM_PRIMARY` to control which is tried first.

| Provider | Env Var | Default Model | Speed |
|---|---|---|---|
| Groq | `GROQ_API_KEY` | `llama-3.3-70b-versatile` | Fastest |
| Gemini | `GOOGLE_API_KEY` | `gemini-2.0-flash-exp` | Fast |
| Cerebras | `CEREBRAS_API_KEY` | `llama3.1-70b` | Fast |
| NVIDIA NIM | `NVIDIA_API_KEY` | `meta/llama-3.1-70b-instruct` | Medium |
| OpenRouter | `OPENROUTER_API_KEY` | `anthropic/claude-3.5-sonnet` | Medium |
| HuggingFace | `HUGGINGFACE_TOKEN` | `Mistral-7B-Instruct-v0.3` | Fallback |

You do not need all six keys — any single key is enough to run the agent. Having multiple keys gives you automatic failover and zero downtime when one provider has an outage.

---

## Quick Start

### Prerequisites
- Python 3.12+
- Local linters: `hadolint`, `kubeconform`, `shellcheck`

### Install
```bash
git clone https://github.com/nithingowdahm87/devops_agent
cd devops_agent
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### Configure
```bash
cp .env.example .env
# Edit .env — add your API keys. Never commit .env.
```

### Run
```bash
# Production mode (strict policy enforcement)
./run_agent.sh --env prod

# Dev mode (relaxed policies)
./run_agent.sh

# Zero-LLM deterministic template mode
./run_agent.sh --no-llm
```

## Project Structure
```text
devops_agent/
├── main.py                        # CLI entry point
├── run_agent.sh                   # Shell wrapper
├── .env.example                   # Env template — copy to .env
├── requirements.txt               # Python deps
├── src/
│   └── engine/
│       ├── llm.py                 # 6-provider LLM router + fallback loop
│       ├── config.py              # Central env config loader
│       ├── compiler_pipeline.py   # Master pipeline controller
│       ├── graph.py               # Immutable Architecture Graph
│       ├── integrity.py           # Cross-artifact consistency auditor
│       ├── healer.py              # OODA healing loop
│       ├── policy_engine.py       # Prod/dev policy enforcement
│       ├── rag.py                 # RAG context retrieval
│       ├── validate.py            # Schema + semantic validation
│       └── scoring.py             # Production readiness score
├── configs/
│   └── prompts/
│       ├── docker/
│       │   ├── docker_production.md   # 20-rule Dockerfile generator
│       │   └── docker_compose.md      # Compose generator rules
│       ├── k8s/
│       │   └── k8s_production.md      # CIS Benchmark K8s generator
│       └── cicd/
│           └── cicd_production.md     # GitHub Actions DevSecOps generator
└── tests/
```

## Prompt Standards
All prompts follow a 4-step structure used by production DevSecOps teams:

1. **Analyze** — inspect project files before writing a single line
2. **Rules** — numbered, named, never-skip rules with exact code examples
3. **Self-audit** — checkbox list the agent runs on its own output
4. **Output format** — exact filenames and file paths the agent must produce

Prompts are stored in `configs/prompts/` and are loaded by the RAG engine at runtime.

| Prompt File | Covers | Rules Count |
|---|---|---|
| docker/docker_production.md | Dockerfile (5 languages) | 13 rules |
| docker/docker_compose.md | docker-compose.yml | 10 rules |
| k8s/k8s_production.md | Namespace/Deploy/HPA/PDB/NetworkPolicy | 12 rules |
| cicd/cicd_production.md | GitHub Actions full pipeline | 10 rules |

## Security
- API keys are loaded from `.env` only — never hardcoded in source
- `.env` is blocked by `.gitignore`
- Containers run as UID 10001 (non-root, not a system UID)
- No debugging tools (curl, wget, bash) in runtime images
- All CI pipelines run Gitleaks, Trivy FS, Trivy Image, and OWASP ZAP scans
- SARIF results uploaded to GitHub Security tab on every run

## Requirements
```text
openai>=1.0.0
google-generativeai>=0.8.0
python-dotenv>=1.0.0
pyyaml>=6.0
jsonschema>=4.0
requests>=2.31
```
