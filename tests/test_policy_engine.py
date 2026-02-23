# -*- coding: utf-8 -*-
import pytest
from src.models.domain import ProjectModel, Service
from src.engine.policy_engine import PolicyEngine
from src.engine.severity import Severity

def test_policy_env_isolation():
    """Verify that PROD policies are strictly enforced while DEV allows relaxation."""
    prod_model = ProjectModel(project_name="test", environment="prod", services=[])
    dev_model = ProjectModel(project_name="test", environment="dev", services=[])
    
    prod_engine = PolicyEngine(prod_model)
    dev_engine = PolicyEngine(dev_model)
    
    # K8s Deployment missing resources/probes
    bad_k8s = "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: app"
    
    # Prod should fail (HIGH severity)
    prod_findings = prod_engine.validate_artifact("manifest.yaml", bad_k8s)
    assert any(f[0] == Severity.HIGH for f in prod_findings)
    assert any("PROD_POLICY_VIOLATION" in f[1] for f in prod_findings)
    
    # Dev should pass
    dev_findings = dev_engine.validate_artifact("manifest.yaml", bad_k8s)
    assert len(dev_findings) == 0

def test_no_stub_echo_policy():
    """Verify that placeholder echo steps are blocked in all environments."""
    engine = PolicyEngine(ProjectModel(project_name="test", environment="dev", services=[]))
    bad_ci = "steps:\n  - run: echo \"Running Trivy scan...\" # placeholder"
    
    findings = engine.validate_artifact("main.yml", bad_ci)
    assert any(f[0] == Severity.HIGH and "STUB_ECHO" in f[1] for f in findings)
