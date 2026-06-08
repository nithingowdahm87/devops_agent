# DevOps Agent v2.0.0 (GitOps Ready)

Production-grade AI agent that compiles Dockerfiles, Kubernetes manifests, and CI/CD pipelines from raw codebases. Deterministic compiler architecture with multi-provider LLM routing and a production GitOps generator.

---

## Architecture (v2.0.0 Overhaul)

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
│ Stage 2 — LLM Router (Multi-Provider)                      │
│ Kimchi CLI API / Local Ollama / Remote APIs (fallback chain)│
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

## LLM Provider Modes

The agent supports three LLM modes via `--llm-mode`. Use the mode that best fits your infrastructure and security requirements.

| Mode | Provider | Setup | Speed |
|------|----------|-------|-------|
| `kimchi` (default) | Kimchi CLI API | Auto-reads `~/.config/kimchi/harness/auth.json` | ~10-60s |
| `local` | llama.cpp / Ollama | Requires local model server | ~30-120s |
| `remote` | Groq / Gemini / Cerebras / NVIDIA / OpenRouter | Requires API keys in `.env` | ~5-30s |

### Kimchi CLI API (Recommended)

The default mode uses the Kimchi CLI API, which auto-detects your existing authentication token from `~/.config/kimchi/harness/auth.json`. No manual API key management required.

**Supported models:**
- `kimi-k2.5`
- `kimi-k2.6`
- `minimax-m2.5`
- `minimax-m2.7`
- `nemotron-3-super-fp4`

### Local Mode

Uses a local llama.cpp server or Ollama at `http://localhost:8080/v1`. Fully offline once the model is downloaded.

**Recommended models for 8 GB RAM:**

For an 8 GB RAM laptop (WSL + Docker), use lightweight Llama 3.2 models:

```bash
# Install Ollama (Linux/Mac)
/bin/bash -c "$(curl -fsSL https://ollama.com/install.sh)"

# Pull a lightweight model (recommended for 8 GB RAM)
ollama pull llama3.2:3b
# or, for very low RAM:
# ollama pull llama3.2:1b
```

The model name must match the `OLLAMA_MODEL` value in your `.env` file.

### Remote Mode

Uses external API providers. Set API keys in your `.env` file:

- `GROQ_API_KEY`
- `GOOGLE_API_KEY`
- `CEREBRAS_API_KEY`
- `NVIDIA_API_KEY`
- `OPENROUTER_API_KEY`

Remote mode automatically falls back through the provider chain if one is unavailable.

---

## Quick Start

### Prerequisites
- Python 3.10+
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
# 1. Copy and edit the environment template
cp .env.example .env
# Edit .env and set your API keys or LLM mode preferences

# 2. Initialize the local RAG Database (seeds prompts into ChromaDB)
python3 -m scripts.seed_rag_from_prompts
```

### Run
```bash
# Using Kimchi CLI API (default — no key needed if logged in)
./run_agent.sh --llm-mode kimchi /path/to/project

# Using local Ollama/llama.cpp
./run_agent.sh --llm-mode local /path/to/project

# Using remote APIs (requires keys in .env)
./run_agent.sh --llm-mode remote /path/to/project

# Production mode (strict policy enforcement)
./run_agent.sh --llm-mode kimchi --env prod /path/to/project

# Dev mode (relaxed policies)
./run_agent.sh --llm-mode kimchi /path/to/project

# Non-interactive (no extra customization questions)
./run_agent.sh --llm-mode kimchi --no-prompts /path/to/project

# Zero-LLM deterministic template mode
./run_agent.sh --no-llm /path/to/project

# GitOps Mode (Automated Repo Setup + PRs)
./run_agent.sh --llm-mode kimchi --gitops --gitops-repo https://github.com/org/gitops-infra /path/to/project

# Targeted Single-Service Run
./run_agent.sh --llm-mode kimchi --service auth-service --gitops /path/to/project
```

## GitOps Mode

When `--gitops` is enabled, the agent orchestrates a full GitOps transformation:

1. **Per-Service CI**: Generates `.github/workflows/{{svc}}-ci.yml` with scoped path triggers.
2. **ArgoCD Support**: Generates `ApplicationSet` and namespaced Kubernetes files.
3. **Multi-Repo Sync**: Clones/Pulls the `--gitops-repo` and automatically creates PRs or commits if `GITHUB_TOKEN` is present.
4. **Isolated Context**: Each service receives its own resource profile (CPU/RAM) and metadata.

### Required Secrets for GitOps automation

To fully utilize the v2.0.0 proactive PR integration and CI workflows, ensure these environment variables are set during generation, or added to your actual target repository:

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
- Path-traversal protection in file operations
- API key security — auto-reads Kimchi CLI auth token from `~/.config/kimchi/harness/auth.json`
- Containers run as UID 10001 (non-root, not a system UID)
- No debugging tools (curl, wget, bash) in runtime images
- All CI pipelines run Gitleaks, Trivy FS, Trivy Image, and OWASP ZAP scans
- SARIF results uploaded to GitHub Security tab on every run
- Artifact output sanitization — strips reasoning text from generated configs

## Requirements

```text
langchain
langgraph
langchain-google-genai
requests
pyyaml
pydantic>=2.0
python-dotenv>=1.0.0
requests>=2.31.0
```

---

## Changelog v2.0.0

- Multi-provider LLM routing (Kimchi / Local / Remote)
- API key security — auto-reads Kimchi CLI auth token
- Path-traversal protection in file operations
- Artifact output sanitization — strips reasoning text from generated configs
- 120s health check timeout support for Cloudflare-proxied APIs
- Graceful fallback when chromadb is not installed