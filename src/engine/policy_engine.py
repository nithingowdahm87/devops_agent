# -*- coding: utf-8 -*-
import logging
from typing import List, Tuple
from src.engine.severity import Severity
from src.models.domain import ProjectModel

logger = logging.getLogger("devops-agent")

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
        
        # 1. Global: No stub echo steps
        if "echo \"running" in content.lower() or "echo \"placeholder" in content.lower():
            results.append((Severity.HIGH, "STUB_ECHO_DETECTED: Found placeholder echo commands in script."))

        # 2. Environment Specific Policies
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
            if "readinessprobe:" not in c_lower:
                errors.append((Severity.HIGH, "PROD_POLICY_VIOLATION: Missing readinessProbe in Deployment."))
            if "runasnonroot: true" not in c_lower:
                errors.append((Severity.HIGH, "PROD_POLICY_VIOLATION: Prod requires runAsNonRoot: true."))
        
        # Dockerfile Prod Policies
        if "dockerfile" in path.lower():
            if "user " not in c_lower:
                errors.append((Severity.HIGH, "PROD_POLICY_VIOLATION: Dockerfile must define a non-root USER."))
            if ":latest" in c_lower:
                errors.append((Severity.HIGH, "PROD_POLICY_VIOLATION: Avoid using :latest tags in production."))

        return errors

    def _validate_dev(self, path, content) -> List[Tuple[Severity, str]]:
        # Dev is more relaxed
        return []
