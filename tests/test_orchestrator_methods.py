"""
Unit tests for the three extracted V2Orchestrator methods:
  - _build_prompt       (pure prompt assembly)
  - _score_candidates   (heuristic scoring)
  - _validate_and_write (validate + heal + write gate)

All tests run without a real NVIDIA key by patching NvidiaClient.__init__.
"""
import os
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.schemas import ProjectContext
from src.decision_engine.contracts.infra_spec import InfraSpec
from src.decision_engine.contracts.architecture_plan import ArchitecturePlan


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def pin_prompts_root(monkeypatch):
    root = Path(__file__).parent.parent
    monkeypatch.setenv("PROMPTS_ROOT", str(root / "configs" / "prompts"))


@pytest.fixture
def orchestrator(monkeypatch):
    monkeypatch.setenv("LLM_PRIMARY", "nvidia")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    from src.decision_engine.orchestrator import V2Orchestrator
    return V2Orchestrator(environment="dev")


@pytest.fixture
def minimal_context():
    return ProjectContext(
        project_name="test-svc",
        language="javascript/node",
        frameworks=["express"],
        dependencies=["express"],
        ports=["3000"],
        microservice_dirs=[],
        microservice_details={},
    )


@pytest.fixture
def minimal_plan():
    return ArchitecturePlan(
        service_type="api",
        scaling_strategy="horizontal",
        public_exposure=True,
        requires_cache=False,
        requires_queue=False,
        requires_database=False,
        requires_reverse_proxy=True,
        deployment_strategy="rolling",
        observability_level="standard",
    )


# ---------------------------------------------------------------------------
# _build_prompt tests
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_returns_string(self, orchestrator, minimal_context, minimal_plan):
        result = orchestrator._build_prompt("dockerfile", minimal_context, minimal_plan, None, True)
        assert isinstance(result, str)
        assert len(result) > 50

    def test_dockerfile_stage_loads_docker_production_prompt(self, orchestrator, minimal_context, minimal_plan):
        result = orchestrator._build_prompt("dockerfile", minimal_context, minimal_plan, None, True)
        # docker_production.md contains "Dockerfile" guidance
        assert "dockerfile" in result.lower() or "FROM" in result or "docker" in result.lower()

    def test_kubernetes_stage_appends_filename_instruction(self, orchestrator, minimal_context, minimal_plan):
        result = orchestrator._build_prompt("kubernetes", minimal_context, minimal_plan, None, True)
        assert "FILENAME:" in result
        assert "k8s/" in result

    def test_kubernetes_with_resources_appends_resource_block(self, orchestrator, minimal_context, minimal_plan):
        minimal_context.resources = {"cpu_req": "200m", "cpu_lim": "400m", "mem_req": "256Mi", "mem_lim": "512Mi"}
        result = orchestrator._build_prompt("kubernetes", minimal_context, minimal_plan, None, True)
        assert "200m" in result
        assert "256Mi" in result

    def test_dockerfile_with_microservice_dirs_appends_dirs(self, orchestrator, minimal_context, minimal_plan):
        minimal_context.microservice_dirs = ["backend", "frontend"]
        result = orchestrator._build_prompt("dockerfile", minimal_context, minimal_plan, None, True)
        assert "backend" in result
        assert "frontend" in result

    def test_docker_compose_with_services_appends_service_list(self, orchestrator, minimal_context, minimal_plan):
        minimal_context.microservice_dirs = ["api", "worker"]
        minimal_context.microservice_details = {
            "api":    {"ports": ["3000"], "databases": ["PostgreSQL"]},
            "worker": {"ports": ["4000"], "databases": []},
        }
        result = orchestrator._build_prompt("docker_compose", minimal_context, minimal_plan, None, True)
        assert "api" in result
        assert "worker" in result

    def test_unknown_stage_falls_back_gracefully(self, orchestrator, minimal_context, minimal_plan):
        # "scan" maps to debug/healer which exists
        result = orchestrator._build_prompt("scan", minimal_context, minimal_plan, None, True)
        assert isinstance(result, str)

    def test_no_prompts_true_skips_customization_input(self, orchestrator, minimal_context, minimal_plan):
        # Should not call input() when no_prompts=True
        with patch("builtins.input", side_effect=AssertionError("input() called in no_prompts mode")):
            result = orchestrator._build_prompt("kubernetes", minimal_context, minimal_plan, None, True)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _score_candidates tests
# ---------------------------------------------------------------------------

class TestScoreCandidates:
    def _make_spec(self, content: str) -> InfraSpec:
        return InfraSpec(file_content=content, model_name="test")

    def test_dockerfile_multistage_gets_higher_score(self, orchestrator):
        good = self._make_spec("FROM node:20 AS builder\nUSER appuser\nHEALTHCHECK CMD node -e 'ok'\nRUN npm ci")
        bad  = self._make_spec("FROM node:latest\nRUN npm install")
        orchestrator._score_candidates([good, bad], "dockerfile")
        assert good.security_score > bad.security_score

    def test_dockerfile_latest_tag_penalised(self, orchestrator):
        pinned = self._make_spec("FROM node:20-alpine AS builder\nUSER appuser")
        latest = self._make_spec("FROM node:latest AS builder\nUSER appuser")
        orchestrator._score_candidates([pinned, latest], "dockerfile")
        assert pinned.security_score > latest.security_score

    def test_kubernetes_with_hpa_and_probes_scores_higher(self, orchestrator):
        good = self._make_spec("hpa\nnetworkpolicy\nrequests:\nlimits:\nlivenessprobe\nreadinessprobe")
        bare = self._make_spec("apiVersion: apps/v1\nkind: Deployment")
        orchestrator._score_candidates([good, bare], "kubernetes")
        assert good.security_score > bare.security_score

    def test_privileged_true_penalised(self, orchestrator):
        safe      = self._make_spec("FROM node:20-alpine\nUSER appuser")
        privileged = self._make_spec("FROM node:20-alpine\nprivileged: true")
        orchestrator._score_candidates([safe, privileged], "dockerfile")
        assert safe.security_score > privileged.security_score

    def test_cicd_with_trivy_scores_higher(self, orchestrator):
        secure = self._make_spec("trivy scan\npermissions:\nneeds: build")
        plain  = self._make_spec("run: npm test")
        orchestrator._score_candidates([secure, plain], "github_actions")
        assert secure.security_score > plain.security_score

    def test_best_practice_score_set_for_all_candidates(self, orchestrator):
        specs = [self._make_spec("FROM node:20 AS builder\nWORKDIR /app\nCMD [\"node\"]")]
        orchestrator._score_candidates(specs, "dockerfile")
        assert specs[0].best_practice_score > 0

    def test_scores_clamped_to_0_100(self, orchestrator):
        # Pile on every bonus to verify ceiling
        spec = self._make_spec(
            "from node:20 as builder\nuser appuser\nhealthcheck cmd\nnpm ci\n"
            "hpa\nnetworkpolicy\npoddisruptionbudget\nrequests:\nlimits:\n"
            "livenessprobe\nreadinessprobe\ntrivy\npermissions:\nneeds:"
        )
        orchestrator._score_candidates([spec], "dockerfile")
        assert 0 <= spec.security_score <= 100
        assert 0 <= spec.best_practice_score <= 100


# ---------------------------------------------------------------------------
# _validate_and_write tests
# ---------------------------------------------------------------------------

class TestValidateAndWrite:
    @pytest.fixture
    def policy_engine(self):
        from src.engine.policy_engine import PolicyEngine, ProjectModel
        return PolicyEngine(ProjectModel(project_name="test", services=[], environment="dev"))

    def test_valid_dockerfile_written_to_disk(self, orchestrator, tmp_path, policy_engine):
        content = (
            "FILENAME: Dockerfile\n"
            "```dockerfile\n"
            "FROM node:20-alpine AS builder\n"
            "WORKDIR /app\n"
            "COPY package*.json ./\n"
            "RUN npm ci\n"
            "FROM node:20-alpine\n"
            "USER appuser\n"
            "EXPOSE 3000\n"
            "CMD [\"node\", \"server.js\"]\n"
            "```\n"
        )
        files = orchestrator._validate_and_write(
            content, "dockerfile", str(tmp_path), "dev", "myservice", policy_engine, no_heal=True
        )
        assert len(files) == 1
        assert "myservice" in files[0].path
        written = [f for f in tmp_path.rglob("Dockerfile") if ".artifacts_history" not in str(f)]
        assert len(written) == 1

    def test_multiple_filename_blocks_produce_multiple_files(self, orchestrator, tmp_path, policy_engine):
        content = (
            "FILENAME: k8s/deployment.yaml\n"
            "```yaml\napiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: svc\n```\n"
            "FILENAME: k8s/service.yaml\n"
            "```yaml\napiVersion: v1\nkind: Service\nmetadata:\n  name: svc\n```\n"
        )
        files = orchestrator._validate_and_write(
            content, "kubernetes", str(tmp_path), "dev", "svc", policy_engine, no_heal=True
        )
        assert len(files) == 2

    def test_no_filename_blocks_uses_fallback_path(self, orchestrator, tmp_path, policy_engine):
        content = "version: '3.9'\nservices:\n  app:\n    build: .\n    ports:\n      - '3000:3000'\n"
        files = orchestrator._validate_and_write(
            content, "docker_compose", str(tmp_path), "dev", None, policy_engine, no_heal=True
        )
        assert len(files) == 1
        assert "docker-compose" in files[0].path or "shared" in files[0].path

    def test_malformed_filename_token_skipped(self, orchestrator, tmp_path, policy_engine):
        # A FILENAME token longer than 255 chars should be skipped
        long_path = "x" * 300
        content = (
            f"FILENAME: {long_path}\n"
            "```yaml\napiVersion: v1\nkind: Service\n```\n"
        )
        files = orchestrator._validate_and_write(
            content, "kubernetes", str(tmp_path), "dev", None, policy_engine, no_heal=True
        )
        assert len(files) == 0

    def test_output_path_per_service(self, orchestrator):
        path = orchestrator._output_path("Dockerfile", "dockerfile", "backend")
        assert path.startswith("outputs/per-service/backend/")

    def test_output_path_shared_for_compose(self, orchestrator):
        path = orchestrator._output_path("docker-compose.yml", "docker_compose", None)
        assert path.startswith("outputs/shared/")

    def test_output_path_gitops_strips_prefix(self, orchestrator):
        path = orchestrator._output_path("gitops/argocd/app.yaml", "gitops_manifests", None)
        assert path.startswith("gitops-repo/")
        assert "gitops/gitops" not in path
