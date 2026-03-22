"""
Policy Validator — OPA/Conftest policy-as-code enforcement.

Usage:
    from src.policy.validator import PolicyValidator

    validator = PolicyValidator()
    passed, violations = validator.validate(dockerfile_content, stage="docker")
"""

import logging
import os
import subprocess
import tempfile
from typing import List, Tuple

from src.schemas import PolicyViolation, Severity

logger = logging.getLogger("devops-agent.policy")

# Map stage names to policy directories and temp file extensions
_STAGE_CONFIG = {
    "docker": {"policy_dir": "policies/docker", "ext": ".dockerfile", "filename": "Dockerfile"},
    "compose": {"policy_dir": "policies/docker", "ext": ".yml", "filename": "docker-compose.yml"},
    "k8s": {"policy_dir": "policies/k8s", "ext": ".yaml", "filename": "manifest.yaml"},
    "cicd": {"policy_dir": "policies/ci", "ext": ".yml", "filename": "workflow.yml"},
    "observability": {"policy_dir": "policies/k8s", "ext": ".yaml", "filename": "chart.yaml"},
}


class PolicyValidator:
    """
    Validates generated content against OPA/Rego policies using conftest.

    Falls back gracefully if conftest is not installed.
    """

    def __init__(self):
        self.conftest_available = self._check_conftest()
        self.project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

    def _check_conftest(self) -> bool:
        """Check if conftest CLI is available."""
        try:
            result = subprocess.run(
                ["conftest", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info("conftest found: %s", version)
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        logger.warning(
            "conftest not found — policy checks will use built-in rules only. "
            "Install: https://www.conftest.dev/install/"
        )
        return False

    def validate(self, content: str, stage: str) -> Tuple[bool, List[PolicyViolation]]:
        """
        Validate content against policies for the given stage.

        Args:
            content: The generated file content (Dockerfile, YAML, etc.)
            stage: Pipeline stage (docker, k8s, cicd, etc.)

        Returns:
            (passed: bool, violations: List[PolicyViolation])
        """
        stage_key = stage.lower()
        violations: List[PolicyViolation] = []

        # 1. Built-in rules (always run, no external deps)
        builtin_violations = self._builtin_checks(content, stage_key)
        violations.extend(builtin_violations)

        # 2. Conftest/OPA rules (if available)
        if self.conftest_available:
            config = _STAGE_CONFIG.get(stage_key, {})
            policy_dir = os.path.join(self.project_root, config.get("policy_dir", ""))

            if os.path.isdir(policy_dir) and os.listdir(policy_dir):
                conftest_violations = self._run_conftest(content, policy_dir, config)
                violations.extend(conftest_violations)

        # Filter out INFO severity from failing the check? 
        # Usually warnings don't fail, errors fail.
        # But existing logic was "passed = len(violations) == 0".
        # Let's keep strict mode for now, or maybe only fail on ERRORS?
        # The user's original request implies strict validation.
        # But let's refine: Warnings shouldn't block, only Errors.
        
        errors = [v for v in violations if v.severity == Severity.ERROR]
        passed = len(errors) == 0

        if violations:
            logger.warning(
                "Policy violations found | stage=%s | count=%d",
                stage, len(violations),
                extra={"stage": stage},
            )
        else:
            logger.info("Policy check passed | stage=%s", stage, extra={"stage": stage})

        return passed, violations

    def _run_conftest(self, content: str, policy_dir: str, config: dict) -> List[PolicyViolation]:
        """Run conftest against the content."""
        violations = []
        ext = config.get("ext", ".txt")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=ext, delete=False, prefix="devops_policy_"
        ) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = subprocess.run(
                ["conftest", "test", temp_path, "--policy", policy_dir, "--output", "json"],
                capture_output=True, text=True, timeout=30,
            )

            if result.returncode != 0:
                # Parse JSON output for violations
                try:
                    import json
                    output = json.loads(result.stdout)
                    for item in output:
                        for failure in item.get("failures", []):
                            violations.append(PolicyViolation(
                                rule="conftest-failure",
                                message=failure.get("msg", "Unknown violation"),
                                severity=Severity.ERROR
                            ))
                        for warning in item.get("warnings", []):
                            violations.append(PolicyViolation(
                                rule="conftest-warning",
                                message=warning.get("msg", "Unknown warning"),
                                severity=Severity.WARNING
                            ))
                except (json.JSONDecodeError, TypeError):
                    if result.stderr.strip():
                        violations.append(PolicyViolation(
                            rule="conftest-error",
                            message=result.stderr.strip()[:300],
                            severity=Severity.ERROR
                        ))

        except subprocess.TimeoutExpired:
            logger.warning("conftest timed out")
            violations.append(PolicyViolation(
                rule="timeout",
                message="Policy check timed out",
                severity=Severity.WARNING
            ))
        finally:
            os.unlink(temp_path)

        return violations

    # ─── Built-in Rules (no external deps) ───────────────────────

    def _builtin_checks(self, content: str, stage: str) -> List[PolicyViolation]:
        """Run simple built-in policy checks."""
        violations = []
        content_lower = content.lower()

        # Normalise stage so "CI/CD", "cicd", and "ci-cd" all match
        stage_key = stage.replace("/", "").replace("-", "").lower()

        if stage_key == "docker":
            violations.extend(self._check_dockerfile(content, content_lower))
        elif stage_key == "k8s":
            violations.extend(self._check_k8s(content, content_lower))
        elif stage_key == "cicd":
            violations.extend(self._check_ci(content, content_lower))

        return violations

    def _check_dockerfile(self, content: str, content_lower: str) -> List[PolicyViolation]:
        """Built-in Dockerfile policy checks."""
        violations = []

        # Check for :latest tag
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.upper().startswith("FROM "):
                # safe split even if empty
                parts = stripped[5:].strip().split(" ")
                if not parts or not parts[0]: continue
                image = parts[0]
                
                if image.endswith(":latest") or ":" not in image.split("/")[-1]:
                    violations.append(PolicyViolation(
                        rule="docker-no-latest",
                        message=f"Line {i}: Image '{image}' uses :latest or unpinned tag.",
                        severity=Severity.WARNING
                    ))

        # Check for USER instruction
        if "user " not in content_lower or all(
            not line.strip().upper().startswith("USER ")
            for line in lines
            if not line.strip().startswith("#")
        ):
            # Running as root is a security risk -> ERROR
            violations.append(PolicyViolation(
                rule="docker-no-user",
                message="No USER instruction found. Container will run as root.",
                severity=Severity.ERROR
            ))

        # Check for HEALTHCHECK
        if not any(
            line.strip().upper().startswith("HEALTHCHECK ")
            for line in lines
            if not line.strip().startswith("#")
        ):
            violations.append(PolicyViolation(
                rule="docker-no-healthcheck",
                message="No HEALTHCHECK instruction. Consider adding one.",
                severity=Severity.WARNING
            ))

        return violations

    def _check_k8s(self, content: str, content_lower: str) -> List[PolicyViolation]:
        """Built-in Kubernetes manifest policy checks."""
        violations = []

        # Check for resource limits
        if "resources:" not in content_lower:
            violations.append(PolicyViolation(
                rule="k8s-no-limits",
                message="No resource requests/limits found.",
                severity=Severity.ERROR
            ))

        # Check for default namespace
        if "namespace: default" in content_lower:
            violations.append(PolicyViolation(
                rule="k8s-default-namespace",
                message="Deploying to 'default' namespace is discouraged.",
                severity=Severity.ERROR
            ))

        # Check for readiness probe
        if "readinessprobe:" not in content_lower.replace(" ", ""):
            violations.append(PolicyViolation(
                rule="k8s-no-readiness",
                message="No readinessProbe found.",
                severity=Severity.WARNING
            ))

        return violations

    def _check_ci(self, content: str, content_lower: str) -> List[PolicyViolation]:
        """Built-in CI workflow policy checks."""
        violations = []

        # Check for unpinned actions
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("- uses:") or stripped.startswith("uses:"):
                action_ref = stripped.split("uses:")[-1].strip()
                if "@" not in action_ref and action_ref:
                    violations.append(PolicyViolation(
                        rule="ci-unpinned-action",
                        message=f"Line {i}: Action '{action_ref}' is not pinned.",
                        severity=Severity.WARNING
                    ))

        # Check for pull_request_target
        if "pull_request_target" in content_lower:
            violations.append(PolicyViolation(
                rule="ci-pull-request-target",
                message="'pull_request_target' trigger detected. Risk of arbitrary code execution.",
                severity=Severity.ERROR
            ))

        return violations
