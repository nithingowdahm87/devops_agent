# DevOps AI Agent Pipeline v15.0 [Sovereign Architecture]

Welcome to the **Verified S* Sovereign Pipeline**, the definitive industry-leading architecture for generating production-ready DevOps artifacts (Docker, Kubernetes, CI/CD).

Unlike amateur models that allow multiple LLMs to fight over unstructured text, this pipeline utilizes a strict, mathematically sound 6-layer architecture. It leverages an Elite LLM (like Groq's Llama-3.3-70b) for structured generation, deterministic linters for ground-truth validation, and async multi-LLM networks for continuous innovation. 

---

## 🏗 Architecture Details

Every LLM has a named, non-overlapping job. No LLM generates files AND reviews files. Each one does exactly what it is best at, and then steps aside.

The engine follows this precise flow for every run:

1. **Layer 0 (Spec & Research)**: Before writing code, the `Planner` agent establishes a firm architectural contract (`spec.md`). The `Researcher` agent fetches 2026 industry best practices for the exact stack.
2. **Layer 1 (RAG Knowledge Injection)**: Validated Golden Paths (Docker best practices, CIS benchmarks) and past successful innovations are pulled from a local ChromaDB vector store and injected as strict context.
3. **Layer 2 (Self-Consistent Sampler)**: The Elite generation model runs 3 parallel generation threads at varying temperatures (`0.2, 0.4, 0.6`). The system evaluates the batch and selects the consensus structural winner, bypassing standard LLM hallucinations.
4. **Layer 3 (Constitutional Critique)**: The winning candidate is rigorously audited by a semantic reviewer for advanced security posture (e.g. least privilege, layer ordering, secret hygiene).
5. **Layer 4 & 5 (Deterministic Validation & Surgical Healing Loop)**: The resulting YAML/Dockerfile is parsed through static, non-LLM, mathematical linters (`hadolint`, `kubeconform`). If an exact rule ID (e.g. `DL3008`) is violated, the `Healer` executes a surgical retry loop (max 3 times).
6. **Layer 6 (Innovation Flywheel)**: Once a configuration completes and passes linting, a background async process queries models (Groq, Gemini, Nvidia) to critique the final output for performance and modernization. These insights are saved directly back into Layer 1's RAG store, making the agent permanently smarter after every single execution.

---

## ✨ Integrated Modern Features

- **Microservices Awareness**: Automatically detects multi-service architectures (Express, React, Vite) and generates isolated Dockerfiles with shared networking.
- **Reverse Proxy Support**: Native Nginx logic for `docker-compose` and Kubernetes `ConfigMaps`, ensuring your services are production-ready with a consistent entry point.
- **Heuristic Validation Loop**: Uses `hadolint` and `kubeconform` to verify every artifact before it touches your disk.

---

## 🚀 Quick Start / Installation

This setup is designed to be easily portable. If you clone this repository to a new machine, follow these steps:

### 1. Prerequisites
- Python 3.12+ 
- Local linters: `hadolint` (for Docker), `kubeconform` (for K8s), `actionlint` (optional for CI/CD)

### 2. Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
*(Note: The first time you run the agent, it will automatically download an ONNX model for the ChromaDB vector embeddings. This is a one-time setup penalty of ~80MB and may take a few minutes depending on your internet connection.)*

### 3. Environment Variables
Copy `.env.example` to `.env` (or create a `.env` file):
```env
GROQ_API_KEY=your_groq_api_key_here
```
The architecture currently defaults to using `GroqClient` for extreme low-latency inference. 

---

## 🛠 Running the Model

The absolute easiest way to run the pipeline is using the provided `run_agent.sh` script, which automatically sources the virtual environment and `.env` variables for you.

Simply point the orchestrator at your local repository:

```bash
# Start the interactive CLI
./run_agent.sh
```

Or run it directly targeting a path and task:
```bash
# Generate Dockerfile + Kubernetes + CI/CD sequentially 
./run_agent.sh all

# When prompted, enter your path, e.g.
# > Enter project path: sample_app

# Alternatively, run one specific task:
./run_agent.sh docker
./run_agent.sh k8s
./run_agent.sh ci
```

### Prompt Input
The system will ask you for any **custom requirements**. If you hit Enter, it defaults to: *"Generate production-ready infrastructure artifacts following all standard industry best practices."*

---

## 📁 Project Structure

```text
devops-agent/
├── agent.py                 # Main CLI point
├── src/
│   ├── engine/
│   │   ├── orchestrator.py  # Master controller (wires the 6 layers)
│   │   ├── research.py      # Layer 0 (Spec/Research)
│   │   ├── rag.py           # Layer 1 (ChromaDB Vector Store)
│   │   ├── sampler.py       # Layer 2 (Self-Consistency 3x generation)
│   │   ├── constitution.py  # Layer 3 (Semantic self-critique)
│   │   ├── validate.py      # Layer 4 (Deterministic Linter Gate)
│   │   ├── heal.py          # Layer 5 (Surgical Fix Loop)
│   │   └── innovation.py    # Layer 6 (Async Advisory Flywheel)
│   ├── llm_clients/         # Raw API wrappers (Groq/Gemini/Nvidia)
│   └── utils/               # File extractors, static analysis
├── configs/
│   └── prompts/             # Raw engineering guidelines and agent system prompts
└── sample_app/              # The target directory structure for your tests
```
