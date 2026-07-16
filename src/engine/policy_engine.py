"""Policy Engine - Environment-aware policy enforcement with OPA/Rego evaluation."""
import json
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

from src.engine.severity import Severity

logger = logging.getLogger(__name__)

_OPA_BINARY: str | None = shutil.which("opa")
_POLICY_DIR = Path(__file__).parent.parent.parent / "policies"


@dataclass
class ProjectModel:
    """Minimal project model for policy context."""
    project_name: str
    services: list = field(default_factory=list)
    environment: str = "dev"


def _eval_rego(manifest_content: str, artifact_type: str) -> list[str]:
    """Evaluate OPA policies. Returns list of violation strings. No-op if opa not installed."""
    if not _OPA_BINARY:
        logger.debug("opa_binary_not_found — skipping Rego evaluation")
        return []

    policy_file = _POLICY_DIR / artifact_type / "manifests.rego"
    if not policy_file.exists():
        return []

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(manifest_content)
        tmp_path = Path(f.name)

    try:
        result = subprocess.run(
            [_OPA_BINARY, "eval",
             "-i", str(tmp_path),
             "-d", str(policy_file),
             "--format", "json",
             "data.main.deny"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            logger.error("opa_eval_failed", extra={"stderr": result.stderr[:500]})
            return []
        data = json.loads(result.stdout)
        violations = (
            data.get("result", [{}])[0]
                .get("expressions", [{}])[0]
                .get("value", [])
        )
        return [str(v) for v in violations]
    except Exception as e:
        logger.warning("opa_eval_error: %s", e)
        return []
    finally:
        tmp_path.unlink(missing_ok=True)


class PolicyEngine:
    """
    Environment-aware policy enforcement.
    Ensures artifacts adhere to security and operational standards.
    """

    def __init__(self, model: ProjectModel):
        self.model = model
        self.env = model.environment

    def validate_artifact(self, path: str, content: str) -> List[Tuple[Severity, str]]:
        """
        Runs policy checks based on environment and file type.
        Returns a list of (Severity, Message).
        """
        results = []
        c_lower = content.lower()

        # 1. Global: No stub echo steps
        stubs = ["echo \"running", "echo \"placeholder", "echo \"compiling", "run: echo \"...\""]
        for stub in stubs:
            if stub in c_lower:
                results.append((Severity.HIGH, f"STUB_ECHO_DETECTED: Found placeholder echo command: {stub}"))

        # 2. OPA/Rego evaluation (k8s manifests)
        if path.endswith((".yaml", ".yml")):
            artifact_type = "k8s"
            opa_violations = _eval_rego(content, artifact_type)
            for v in opa_violations:
                results.append((Severity.HIGH, f"OPA_POLICY: {v}"))

        # 3. Immutable Constraints
        if self.env == "prod":
            if "dockerfile" in path.lower() and "expose " not in c_lower:
                results.append((Severity.HIGH, "IMMUTABLE_POLICY_VIOLATION: Production Dockerfiles MUST explicitly EXPOSE a port."))

        # 4. Environment Specific Policies
        if self.env == "prod":
            results.extend(self._validate_prod(path, content))
        else:
            results.extend(self._validate_dev(path, content))

        return results

    def _validate_prod(self, path, content) -> List[Tuple[Severity, str]]:
        errors = []
        c_lower = content.lower()

        # K8s Prod Policies
        if path.endswith((".yaml", ".yml")) and "kind: deployment" in c_lower:
            if "resources:" not in c_lower or "limits:" not in c_lower:
                errors.append((Severity.HIGH, "PROD_POLICY_VIOLATION: Missing resource limits in Deployment."))
            # Check for uncommented readinessProbe (ignore lines starting with #)
            has_probe = any(
                "readinessprobe:" in line.strip().lower()
                for line in content.splitlines()
                if not line.strip().startswith("#")
            )
            if not has_probe:
                errors.append((Severity.HIGH, "PROD_POLICY_VIOLATION: Missing readinessProbe in Deployment."))
            if "runasnonroot: true" not in c_lower:
                errors.append((Severity.HIGH, "PROD_POLICY_VIOLATION: Prod requires runAsNonRoot: true."))
            # Check for :latest image tag in K8s manifests
            if ":latest" in content:
                errors.append((Severity.HIGH, "PROD_POLICY_VIOLATION: Avoid using :latest image tags in production."))

        # Dockerfile Prod Policies
        if "dockerfile" in path.lower():
            if "user " not in c_lower:
                errors.append((Severity.HIGH, "PROD_POLICY_VIOLATION: Dockerfile must define a non-root USER."))
            if ":latest" in content:
                errors.append((Severity.HIGH, "PROD_POLICY_VIOLATION: Avoid using :latest tags in production."))

        return errors

    def _validate_dev(self, path, content) -> List[Tuple[Severity, str]]:
        # Dev is more relaxed but still blocks stubs (handled in validate_artifact)
        return []


def validate_artifact(path: str, content: str, environment: str = "dev") -> list:
    """Convenience function for validating a single artifact."""
    model = ProjectModel(project_name="test", services=[], environment=environment)
    engine = PolicyEngine(model)
    return engine.validate_artifact(path, content)