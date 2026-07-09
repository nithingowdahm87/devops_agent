"""
Integration and regression tests for security features and core pipeline.
"""
import os
import tempfile
import pytest
from pathlib import Path


class TestPromptInjectionDefense:
    """Test that prompt injection attempts are blocked."""

    def test_prompt_loader_rejects_extra_keys(self):
        from src.utils.prompt_loader import get_renderer, PromptInjectionError
        renderer = get_renderer()
        template = "Hello {context} and {evil_key}"
        context = {"context": "test", "evil_key": "injection"}
        with pytest.raises(PromptInjectionError):
            renderer.render(template, context)

    def test_prompt_loader_allows_only_allowlisted_keys(self):
        from src.utils.prompt_loader import get_renderer
        renderer = get_renderer()
        template = "Project: {project_name}, Service: {service_name}"
        context = {"project_name": "myapp", "service_name": "backend"}
        result = renderer.render(template, context)
        assert "myapp" in result
        assert "backend" in result

    def test_prompt_loader_truncates_long_values(self):
        from src.utils.prompt_loader import get_renderer, MAX_VAR_SIZES
        renderer = get_renderer()
        long_context = "x" * (MAX_VAR_SIZES["context"] + 100)
        template = "{context}"
        context = {"context": long_context}
        result = renderer.render(template, context)
        assert "[TRUNCATED: EXCEEDS LIMIT]" in result
        assert len(result) <= MAX_VAR_SIZES["context"] + 50

    def test_prompt_loader_detects_suspicious_jinja2_constructs(self):
        from src.utils.prompt_loader import get_renderer, PromptInjectionError
        renderer = get_renderer()
        # Template with suspicious Jinja2 constructs
        template = "{% for x in range(10) %}{{ x }}{% endfor %} {context}"
        context = {"context": "test"}
        with pytest.raises(PromptInjectionError):
            renderer.render(template, context)


class TestPathTraversalProtection:
    """Test that file operations prevent path traversal."""

    def test_safe_path_blocks_traversal(self):
        from src.tools.file_ops import _safe_path
        with pytest.raises(ValueError, match="Path escape attempt"):
            _safe_path("/project", "../../../etc/passwd")

    def test_safe_path_blocks_absolute_outside_root(self):
        from src.tools.file_ops import _safe_path
        with pytest.raises(ValueError, match="Path escape attempt"):
            _safe_path("/project", "/etc/passwd")

    def test_safe_path_allows_valid_relative(self):
        from src.tools.file_ops import _safe_path
        result = _safe_path("/project", "outputs/dockerfile")
        assert result == "/project/outputs/dockerfile"

    def test_safe_path_normalizes_paths(self):
        from src.tools.file_ops import _safe_path
        result = _safe_path("/project", "outputs/../outputs/file")
        assert result == "/project/outputs/file"


class TestProviderFailFast:
    """Test that missing provider config fails fast."""

    def test_orchestrator_fails_without_nvidia_key(self, monkeypatch):
        """V2Orchestrator should raise RuntimeError when NVIDIA_API_KEY not set."""
        monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
        monkeypatch.setenv("LLM_PRIMARY", "nvidia")

        from src.decision_engine.orchestrator import V2Orchestrator
        with pytest.raises(RuntimeError, match="NVIDIA LLM provider not available"):
            V2Orchestrator()

    def test_nvidia_client_fails_without_key(self, monkeypatch):
        """NvidiaClient should raise RuntimeError when NVIDIA_API_KEY not set."""
        monkeypatch.delenv("NVIDIA_API_KEY", raising=False)

        from src.llm_clients.nvidia_client import NvidiaClient
        with pytest.raises(RuntimeError, match="NVIDIA_API_KEY not set"):
            NvidiaClient()


class TestArtifactQuarantine:
    """Test that failed artifacts go to quarantine."""

    def test_artifact_manager_writes_history(self, tmp_path):
        from src.engine.artifact_manager import ArtifactManager
        from src.engine.severity import Severity

        mgr = ArtifactManager(str(tmp_path), "dev")
        mgr.write_gate("outputs/test.txt", "content", Severity.LOW)

        # Check file was written to project path
        assert (tmp_path / "outputs/test.txt").exists()

        # Check history was saved
        history_files = list((tmp_path / ".artifacts_history" / "dev").rglob("test.txt"))
        assert len(history_files) == 1

    def test_artifact_manager_blocks_critical(self, tmp_path):
        from src.engine.artifact_manager import ArtifactManager
        from src.engine.severity import Severity

        mgr = ArtifactManager(str(tmp_path), "dev")
        result = mgr.write_gate("outputs/bad.txt", "bad content", Severity.CRITICAL)

        assert result is False
        # File should NOT be written to project path
        assert not (tmp_path / "outputs/bad.txt").exists()

    def test_artifact_manager_quarantines_high_in_prod(self, tmp_path):
        from src.engine.artifact_manager import ArtifactManager
        from src.engine.severity import Severity

        mgr = ArtifactManager(str(tmp_path), "prod")
        result = mgr.write_gate("outputs/bad.txt", "bad content", Severity.HIGH)

        assert result is False
        # File should be written as .broken
        assert (tmp_path / "outputs/bad.txt.broken").exists()
        assert not (tmp_path / "outputs/bad.txt").exists()


class TestIdempotencyEngine:
    """Test deterministic output normalization."""

    def test_yaml_idempotency(self):
        from src.engine.idempotency import IdempotencyEngine
        yaml_content = """
key1: value1
key2: value2
key3: value3
"""
        result = IdempotencyEngine.stabilize_yaml(yaml_content)
        # Should be deterministic
        assert result == IdempotencyEngine.stabilize_yaml(result)

    def test_dockerfile_normalization(self):
        from src.engine.idempotency import IdempotencyEngine
        dockerfile = """
from node:20-alpine
run npm install
cmd ["node", "app.js"]
"""
        result = IdempotencyEngine.stabilize_dockerfile(dockerfile)
        # Instructions should be uppercase
        assert "FROM node:20-alpine" in result
        assert "RUN npm install" in result
        assert 'CMD ["node", "app.js"]' in result

    def test_json_idempotency(self):
        from src.engine.idempotency import IdempotencyEngine
        json_content = '{"b": 2, "a": 1}'
        result = IdempotencyEngine.stabilize_json(json_content)
        # Keys should be sorted
        assert result == '{\n  "a": 1,\n  "b": 2\n}'


class TestOrchestratorFlow:
    """Basic orchestrator flow tests with mocked LLM."""

    def test_orchestrator_initializes_with_nvidia(self, monkeypatch):
        """V2Orchestrator should initialize with NVIDIA provider."""
        monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
        monkeypatch.setenv("LLM_PRIMARY", "nvidia")

        from src.decision_engine.orchestrator import V2Orchestrator
        orchestrator = V2Orchestrator()
        assert len(orchestrator.generators) == 1
        assert orchestrator.generators[0].model_name == "NVIDIA"

    def test_stage_prompt_loading(self):
        """Stage prompts should load correctly."""
        from src.utils.prompt_loader import load_prompt

        # These should exist in configs/prompts/
        docker_prompt = load_prompt("docker", "docker_production")
        assert "Dockerfile" in docker_prompt
        assert "multi-stage" in docker_prompt.lower()

        k8s_prompt = load_prompt("k8s", "k8s_production")
        assert "Deployment" in k8s_prompt
        assert "NetworkPolicy" in k8s_prompt

        cicd_prompt = load_prompt("cicd", "github_actions")
        assert "GitHub Actions" in cicd_prompt or "workflow" in cicd_prompt.lower()


class TestConfigValidation:
    """Test configuration validation."""

    def test_env_example_exists(self):
        """Ensure .env.example exists and has required vars."""
        env_example = Path(".env.example")
        assert env_example.exists()
        content = env_example.read_text()
        assert "NVIDIA_API_KEY" in content
        assert "NVIDIA_MODEL" in content

    def test_dockerfile_has_healthcheck(self):
        """Dockerfile should have HEALTHCHECK instruction."""
        dockerfile = Path("Dockerfile").read_text()
        assert "HEALTHCHECK" in dockerfile

    def test_dockerfile_non_root_user(self):
        """Dockerfile should create non-root user."""
        dockerfile = Path("Dockerfile").read_text()
        assert "appuser" in dockerfile
        assert "USER appuser" in dockerfile


# Run with: pytest tests/test_security_and_integration.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])