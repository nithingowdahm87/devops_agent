"""
Integration test: full pipeline against sample-node-app/ with mocked NvidiaClient.
Exercises the FILENAME: parser, ArtifactManager, Validator, and PolicyEngine
without making real LLM calls.
"""
import shutil
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Canned LLM responses — exercise the full FILENAME: multifile parser
# ---------------------------------------------------------------------------

_DOCKERFILE_FIXTURE = """\
FILENAME: Dockerfile
```dockerfile
# syntax=docker/dockerfile:1
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --ignore-scripts && npm cache clean --force
COPY . .

FROM node:20-alpine AS runtime
RUN addgroup -g 10001 -S appgroup && adduser -u 10001 -S appuser -G appgroup
WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/server.js ./
USER appuser
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \\
  CMD node -e "require('http').get('http://localhost:3000/health',(r)=>{process.exit(r.statusCode===200?0:1)}).on('error',()=>process.exit(1))"
CMD ["node", "server.js"]
```
"""

_K8S_FIXTURE = """\
FILENAME: k8s/deployment.yaml
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sample-node-app
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: sample-node-app
  template:
    metadata:
      labels:
        app: sample-node-app
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
      containers:
        - name: sample-node-app
          image: sample-node-app:1.0.0
          ports:
            - containerPort: 3000
          resources:
            requests: {cpu: "100m", memory: "128Mi"}
            limits:   {cpu: "500m", memory: "512Mi"}
          readinessProbe:
            httpGet: {path: /health, port: 3000}
            initialDelaySeconds: 10
```
FILENAME: k8s/service.yaml
```yaml
apiVersion: v1
kind: Service
metadata:
  name: sample-node-app
spec:
  selector:
    app: sample-node-app
  ports:
    - port: 80
      targetPort: 3000
```
"""

_CI_FIXTURE = """\
FILENAME: .github/workflows/ci.yml
```yaml
name: CI
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: {node-version: "20"}
      - run: npm ci
      - run: npm test
```
"""

_COMPOSE_FIXTURE = """\
FILENAME: docker-compose.yml
```yaml
version: "3.9"
services:
  app:
    build: .
    ports:
      - "3000:3000"
```
"""

_FIXTURE_MAP = {
    "dockerfile":     _DOCKERFILE_FIXTURE,
    "kubernetes":     _K8S_FIXTURE,
    "github_actions": _CI_FIXTURE,
    "cicd":           _CI_FIXTURE,
    "docker_compose": _COMPOSE_FIXTURE,
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def repo_root(monkeypatch):
    """Pin PROMPTS_ROOT so prompt_loader resolves correctly regardless of CWD."""
    import pathlib
    root = pathlib.Path(__file__).parent.parent
    monkeypatch.setenv("PROMPTS_ROOT", str(root / "configs" / "prompts"))


@pytest.fixture
def mock_nvidia(monkeypatch):
    """Patch NvidiaClient.call to return stage-appropriate fixture content."""
    def _fake_call(self, prompt: str, **kwargs) -> str:
        prompt_lower = prompt.lower()
        for stage_key, fixture in _FIXTURE_MAP.items():
            if stage_key.replace("_", " ") in prompt_lower or stage_key in prompt_lower:
                return fixture
        return _DOCKERFILE_FIXTURE  # safe default

    monkeypatch.setattr(
        "src.llm_clients.nvidia_client.NvidiaClient.call",
        _fake_call,
    )
    # Also patch the key check so NvidiaClient.__init__ doesn't raise
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key-for-integration")


@pytest.fixture
def node_app_copy(tmp_path):
    src = Path("sample-node-app")
    if not src.exists():
        pytest.skip("sample-node-app/ not found — skipping integration test")
    dest = tmp_path / "app"
    shutil.copytree(str(src), str(dest))
    return dest


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_full_pipeline_generates_dockerfile(node_app_copy, mock_nvidia, monkeypatch):
    import os
    monkeypatch.setenv("LLM_PRIMARY", "nvidia")
    monkeypatch.chdir(node_app_copy.parent)

    from src.analysis.code_analysis_agent import CodeAnalysisAgent
    from src.decision_engine.orchestrator import V2Orchestrator

    context = CodeAnalysisAgent(str(node_app_copy)).get_cached_analysis()
    orch = V2Orchestrator(environment="dev")
    orch.run_pipeline(
        project_path=str(node_app_copy),
        context=context,
        environment="dev",
        no_prompts=True,
        no_heal=True,
    )

    # At least one Dockerfile should exist under outputs/
    dockerfiles = list(node_app_copy.rglob("Dockerfile"))
    assert len(dockerfiles) >= 1, "Expected at least one Dockerfile to be generated"


def test_full_pipeline_generates_k8s_manifests(node_app_copy, mock_nvidia, monkeypatch):
    import os
    monkeypatch.setenv("LLM_PRIMARY", "nvidia")
    monkeypatch.chdir(node_app_copy.parent)

    from src.analysis.code_analysis_agent import CodeAnalysisAgent
    from src.decision_engine.orchestrator import V2Orchestrator

    context = CodeAnalysisAgent(str(node_app_copy)).get_cached_analysis()
    orch = V2Orchestrator(environment="dev")
    orch.run_pipeline(
        project_path=str(node_app_copy),
        context=context,
        environment="dev",
        no_prompts=True,
        no_heal=True,
    )

    yaml_files = list(node_app_copy.rglob("*.yaml")) + list(node_app_copy.rglob("*.yml"))
    k8s_files = [f for f in yaml_files if "outputs" in str(f)]
    assert len(k8s_files) >= 1, "Expected at least one K8s/CI YAML to be generated"


def test_context_cache_cleaned_after_run(node_app_copy, mock_nvidia, monkeypatch):
    monkeypatch.setenv("LLM_PRIMARY", "nvidia")
    monkeypatch.chdir(node_app_copy.parent)

    from src.analysis.code_analysis_agent import CodeAnalysisAgent
    from src.decision_engine.orchestrator import V2Orchestrator

    context = CodeAnalysisAgent(str(node_app_copy)).get_cached_analysis()
    orch = V2Orchestrator(environment="dev")
    orch.run_pipeline(
        project_path=str(node_app_copy),
        context=context,
        environment="dev",
        no_prompts=True,
        no_heal=True,
    )

    # .devops_context.json should be cleaned up after a successful run
    assert not (node_app_copy / ".devops_context.json").exists(), (
        ".devops_context.json should be removed after pipeline completes"
    )


def test_artifact_history_written(node_app_copy, mock_nvidia, monkeypatch):
    monkeypatch.setenv("LLM_PRIMARY", "nvidia")
    monkeypatch.chdir(node_app_copy.parent)

    from src.analysis.code_analysis_agent import CodeAnalysisAgent
    from src.decision_engine.orchestrator import V2Orchestrator

    context = CodeAnalysisAgent(str(node_app_copy)).get_cached_analysis()
    orch = V2Orchestrator(environment="dev")
    orch.run_pipeline(
        project_path=str(node_app_copy),
        context=context,
        environment="dev",
        no_prompts=True,
        no_heal=True,
    )

    history_dir = node_app_copy / ".artifacts_history"
    assert history_dir.exists(), ".artifacts_history/ should be created"
    run_dirs = list(history_dir.rglob("*"))
    assert len(run_dirs) > 0, "At least one artifact should be in history"
