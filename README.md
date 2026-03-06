# DevOps Agent v12.2 (GitOps Ready)

Production-grade AI agent that compiles Dockerfiles, Kubernetes manifests, and CI/CD pipelines from raw codebases. Deterministic compiler architecture with a 6-provider LLM fallback loop and a production GitOps generator.

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
│ Stage 2 — LLM Router (Deterministic Fallback)              │
│ Groq → Gemini → Cerebras → OpenAI → NVIDIA → OpenRouter    │
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

## LLM Providers

The agent uses a **fallback loop** — if the primary provider fails or times out, it automatically tries the next in order.

| Provider | Env Var | Default Model | Speed |
|---|---|---|---|
| Groq | `GROQ_API_KEY` | `llama-3.3-70b-versatile` | Fastest |
| Gemini | `GOOGLE_API_KEY` | `gemini-2.0-flash` | Fast |
| Cerebras | `CEREBRAS_API_KEY` | `llama-3.1-70b-versatile` | Fast |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o-mini` | Stable |
| NVIDIA NIM | `NVIDIA_API_KEY` | `meta/llama-3.1-70b-instruct` | Medium |
| OpenRouter | `OPENROUTER_API_KEY` | `anthropic/claude-3.5-sonnet` | Medium |

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
