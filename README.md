# DevOps Agent v12.2 (GitOps Ready)

Production-grade AI agent that compiles Dockerfiles, Kubernetes manifests, and CI/CD pipelines from raw codebases. Deterministic compiler architecture with a local Ollama LLM and a production GitOps generator.

---

## Architecture (v12.2 Overhaul)

Codebase Input
│
▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 1 — Code Discovery & Per-Service Isolation          │
│ Detects microservices, runtime versions, port assignments  │
└────────────────────────┬────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 2 — LLM Router (Ollama Local)                        │
│ Ollama (llama3.2:3b) → localhost:11434/v1                   │
└────────────────────────┬────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 3 — GitOps Pipeline Generation                       │
│ GitHub Actions (per-svc) / ArgoCD Manifests / Secrets Doc  │
└────────────────────────┬────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 4 — OODA Healing & Schema Validation                 │
│ hadolint / kubeconform / JSON Schema → Healer → Validate   │
└────────────────────────┬────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 5 — Artifact Hierarchy (Outputs)                     │
│ outputs/per-service/ | outputs/shared/ | outputs/docs/     │
└─────────────────────────────────────────────────────────────┘

---

## Local LLM (Ollama-Only)

This agent now uses a **single local LLM provider**: [Ollama](https://ollama.com), via its OpenAI-compatible API at `http://localhost:11434/v1`.

There are **no remote providers** (Groq, OpenAI, Gemini, etc.) in the runtime path anymore — every generation call goes through the local Ollama server.

### Why local only?

- Zero cloud cost, no API keys.
- Works fully offline once the model is pulled.
- Deterministic behavior on a single machine (no cross-DC latency or provider drift).

### Recommended models for 8 GB RAM

For an 8 GB RAM laptop (WSL + Docker), use **lightweight Llama 3.2** models:

- `llama3.2:3b` — default in `.env.example`, good quality and fits 8 GB easily.
- `llama3.2:1b` — extra-light if RAM is very tight or you want maximum speed.

Pull one model before running the agent:

```bash
# Install Ollama (Linux/Mac)
/bin/bash -c "$(curl -fsSL https://ollama.com/install.sh)"

# Pull a lightweight model (recommended for 8 GB RAM)
ollama pull llama3.2:3b
# or, for very low RAM:
# ollama pull llama3.2:1b
```

The model name you pull must match the `OLLAMA_MODEL` value in your `.env` file.

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
# 1. Decode the provided base64 environment variables
base64 -d .env.b64 > .env

# 2. Initialize the local RAG Database (seeds prompts into ChromaDB)
python3 -m scripts.seed_rag_from_prompts
```

### Run
```bash
# Production mode (strict policy enforcement)
./run_agent.sh --env prod

# Dev mode (relaxed policies)
./run_agent.sh

# Non-interactive (no extra customization questions)
./run_agent.sh --no-prompts

# Zero-LLM deterministic template mode
./run_agent.sh --no-llm

# GitOps Mode (Automated Repo Setup + PRs)
./run_agent.sh --gitops --gitops-repo https://github.com/org/gitops-infra

# Targeted Single-Service Run
./run_agent.sh --service auth-service --gitops
```

## GitOps Mode
When `--gitops` is enabled, the agent orchestrates a full GitOps transformation:
1. **Per-Service CI**: Generates `.github/workflows/{{svc}}-ci.yml` with scoped path triggers.
2. **ArgoCD Support**: Generates `ApplicationSet` and namespaced Kubernetes files.
3. **Multi-Repo Sync**: Clones/Pulls the `--gitops-repo` and automatically creates PRs or commits if `GITHUB_TOKEN` is present.
4. **Isolated Context**: Each service receives its own resource profile (CPU/RAM) and metadata.

### Required Secrets for GitOps automation
To fully utilize the V2 proactive PR integration and CI workflows, ensure these environment variables are set during generation, or added to your actual target repository:
- `GITHUB_TOKEN`: For the agent to automatically push to the GitOps repo and open a PR.
- `GITHUB_REPO`: The target repo for the GitOps state (e.g. `your-username/my-infra-repo`).
- `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN`: Required by the generated CI actions to publish your built images.

## Directory Hierarchy
Generated files are organized in `outputs/` to support monorepos cleanly:
```text
outputs/
├── per-service/          # Dockerfiles, CI workflows, and K8s manifests
│   └── <service-name>/
├── shared/               # docker-compose.yml and baseline K8s
│   └── gitops/           # ArgoCD & ApplicationSet manifests
└── docs/                 # Secrets requirements and audit reports
```

## Prompt Standards
All prompts follow a 4-step structure used by production DevSecOps teams:

1. **Analyze** — inspect project files before writing a single line
2. **Rules** — numbered, named, never-skip rules with exact code examples
3. **Self-audit** — checkbox list the agent runs on its own output
4. **Output format** — exact filenames and file paths the agent must produce

Prompts are stored in `configs/prompts/` and are loaded by the RAG engine at runtime.

| Prompt File | Covers | Features |
|---|---|---|
| docker/docker_production.md | Dockerfile (5 languages) | 13 rules, Non-root, Multi-stage |
| k8s/argocd.md | ArgoCD ApplicationSet | App-of-Apps, Auto-heal, Namespacing |
| cicd/github_actions.md | GitHub Actions CI/CD | Path scoped triggers, GitOps Push |
| docs/secrets.md | secrets-required.md | Dependency mapping from code analysis |

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
