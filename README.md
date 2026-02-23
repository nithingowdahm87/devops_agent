# DevOps AI Agent Pipeline v12.0 [Infrastructure Compiler]

Welcome to the **DevOps Agent V12.0**, the definitive industry-leading architecture for generating production-ready DevOps artifacts (Docker, Kubernetes, CI/CD). It is now a 10/10 **Locked Infrastructure Compiler**.

Unlike probabilistic generators, this pipeline utilizes a multi-layer, deterministic compiler architecture. It enforces an immutable **Architecture Graph**, surgical OODA healing loops, and environment-aware security policies.

---

## 🏗 Level 10 Architecture Details

The system transforms raw codebase analysis into a deterministic "Locked Spec," following these precise stages:

1. **Stage 1: Code Discovery & Graphing**: Deep-scans the codebase for languages, frameworks, and hidden database signatures (SQL, .env, properties). It builds an **Immutable Architecture Graph** that serves as the single source of truth.
2. **Stage 2: Model Projection**: Maps the architecture graph to a stable **Domain Model**, pinning LTS versions via real-time lookups (`endoflife.date`).
3. **Stage 3: Generation & Schema Validation**: Generates artifacts (Dockerfile, K8s, CI/CD) and validates them against **Strict JSON Schemas** before any semantic checks.
4. **Stage 4: OODA Healing Loop**: If static analysis (`hadolint`, `kubeconform`) fails, the **Healer** executes an Observe-Orient-Decide-Act loop to surgically repair the code based on exact error feedback.
5. **Stage 5: Policy Enforcement**: Runs the **Policy Engine** to enforce environment-specific constraints (e.g., mandatory non-root users, resource limits, and probe definitions for `prod` mode).
6. **Stage 6: Global Integrity Audit**: Performs a final cross-artifact consistency check. It detects "Port Drift" or "Image Tag Drift" between Dockerfile, Compose, and Kubernetes manifests.

---

## ✨ V12.0 Tier 10 Features

- **Immutable Infrastructure Compiler**: Locked execution order to prevent architectural drift.
- **Surgical OODA Healer**: Precise error feedback loops with deterministic safe fallbacks.
- **Environment Profiles**: Strict `prod` policies vs relaxed `dev` sandboxing.
- **Artifact Observability**: Every file includes an `ArtifactReport` with a **Production Readiness Score**.
- **Real-time LTS Integration**: Dynamic runtime versioning via external API lookup.
- **Idempotency Engine**: Stable sorting and formatting for 0-byte diffs on repeated runs.

---

## 🚀 Quick Start / Installation

### 1. Prerequisites
- Python 3.12+ 
- Local linters: `hadolint`, `kubeconform`

### 2. Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Variables
The agent supports **Gemini**, **Groq**, and **Nvidia** models.
```env
GOOGLE_API_KEY=your_key
NVIDIA_API_KEY=your_key
```

---

## 🛠 Running the Model

The easiest way to run the pipeline is using `run_agent.sh`:

```bash
# Start in Dev mode (default)
./run_agent.sh

# Start in Production mode (Strict Policies)
./run_agent.sh --env prod

# Zero-LLM Deterministic Template mode
./run_agent.sh --no-llm
```

---

## 📁 Level 10 Project Structure

```text
devops-agent/
├── main.py                    # Main CLI Entry Point
├── run_agent.sh               # UTF-8 Enforced Shell Wrapper
├── src/
│   ├── engine/
│   │   ├── compiler_pipeline.py # Master Pipeline Controller
│   │   ├── graph.py             # Immutable Architecture Graph
│   │   ├── policy_engine.py     # Env-aware Security Policies
│   │   ├── integrity.py         # Cross-artifact Consistency Auditor
│   │   ├── healer.py            # OODA Repair Loop
│   │   ├── artifact_manager.py  # Write Gate & History Rollback
│   │   ├── idempotency.py       # Stable Formatter
│   │   └── lts_lookup.py        # Real-time Version Lookup
│   ├── agents/
│   │   └── code_analysis_agent.py # Discovery & DB Detection
│   ├── models/
│   │   └── domain.py            # Immutable Data Models
│   └── tools/                   # File/YAML Extractors
├── configs/
│   └── prompts/               # Elite Engineering Guidelines
└── tests/                     # 17-Test High-Coverage Suite
```
