"""Unit tests for PolicyEngine — prod/dev rules, OPA integration, stub detection."""
import pytest

_COMPLIANT_DEPLOYMENT = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
  namespace: production
spec:
  template:
    spec:
      securityContext:
        runAsNonRoot: true
      containers:
        - name: app
          image: myregistry.io/app:1.2.3
          resources:
            requests: {cpu: "250m", memory: "512Mi"}
            limits:   {cpu: "2",    memory: "2Gi"}
          readinessProbe:
            httpGet: {path: /health, port: 8080}
"""

_LATEST_TAG = _COMPLIANT_DEPLOYMENT.replace("app:1.2.3", "app:latest")
_NO_LIMITS = _COMPLIANT_DEPLOYMENT.replace(
    'limits:   {cpu: "2",    memory: "2Gi"}', ""
)
_NO_PROBE = _COMPLIANT_DEPLOYMENT.replace("readinessProbe:", "# readinessProbe:")
_NO_NON_ROOT = _COMPLIANT_DEPLOYMENT.replace("runAsNonRoot: true", "runAsNonRoot: false")
_STUB_ECHO = 'steps:\n  - run: echo "running tests"\n'

_COMPLIANT_DOCKERFILE = """
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
FROM python:3.11-slim AS runtime
RUN groupadd -g 10001 appgroup && useradd -r -u 10001 -g appgroup appuser
WORKDIR /app
COPY --from=builder /app .
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
"""


def _engine(env: str = "prod"):
    from src.engine.policy_engine import PolicyEngine, ProjectModel
    model = ProjectModel(project_name="test", services=[], environment=env)
    return PolicyEngine(model)


def _violations(content: str, path: str = "deployment.yaml", env: str = "prod") -> list[str]:
    findings = _engine(env).validate_artifact(path, content)
    return [msg for _, msg in findings]


def test_compliant_deployment_passes():
    assert _violations(_COMPLIANT_DEPLOYMENT) == []


def test_rejects_latest_tag_in_prod():
    msgs = _violations(_LATEST_TAG)
    assert any(":latest" in m.lower() for m in msgs)


def test_rejects_missing_resource_limits():
    msgs = _violations(_NO_LIMITS)
    assert any("limit" in m.lower() for m in msgs)


def test_rejects_missing_readiness_probe():
    msgs = _violations(_NO_PROBE)
    assert any("probe" in m.lower() for m in msgs)


def test_rejects_missing_run_as_non_root():
    msgs = _violations(_NO_NON_ROOT)
    assert any("nonroot" in m.lower() or "non-root" in m.lower() or "runasnonroot" in m.lower() for m in msgs)


def test_rejects_stub_echo_globally():
    msgs = _violations(_STUB_ECHO, path="ci.yml", env="dev")
    assert any("stub" in m.lower() or "echo" in m.lower() for m in msgs)


def test_dev_env_allows_latest_tag():
    msgs = _violations(_LATEST_TAG, env="dev")
    # dev policy does not enforce :latest restriction
    assert not any(":latest" in m.lower() for m in msgs)


def test_prod_dockerfile_requires_user():
    dockerfile_no_user = "FROM python:3.11-slim\nRUN pip install flask\nEXPOSE 5000\n"
    msgs = _violations(dockerfile_no_user, path="outputs/per-service/app/Dockerfile", env="prod")
    assert any("user" in m.lower() for m in msgs)


def test_prod_dockerfile_requires_expose():
    dockerfile_no_expose = "FROM python:3.11-slim\nUSER appuser\n"
    msgs = _violations(dockerfile_no_expose, path="outputs/per-service/app/Dockerfile", env="prod")
    assert any("expose" in m.lower() for m in msgs)


def test_compliant_dockerfile_passes():
    assert _violations(_COMPLIANT_DOCKERFILE, path="outputs/per-service/app/Dockerfile") == []
