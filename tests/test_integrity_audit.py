# -*- coding: utf-8 -*-
import pytest
from src.models.domain import ProjectModel, Service
from src.engine.graph import ArchitectureGraph
from src.engine.integrity import IntegrityAuditor
from src.engine.severity import Severity

def test_port_integrity_audit():
    """Verify that IntegrityAuditor detects port drift across Dockerfile and Compose."""
    svc = Service(name="api", language="node", runtime_version="20", base_image="node", port=3000)
    model = ProjectModel(project_name="test", services=[svc], environment="dev")
    graph = ArchitectureGraph(model)
    
    auditor = IntegrityAuditor(graph)
    
    # Correct case
    auditor.add_artifact("Dockerfile", "FROM node\nEXPOSE 3000")
    auditor.add_artifact("docker-compose.yml", "api:\n  ports:\n    - \"8080:3000\"")
    findings = auditor.run_audit()
    assert len(findings) == 0
    
    # Failure case: Dockerfile EXPOSE mismatch
    auditor.artifacts["Dockerfile"] = "FROM node\nEXPOSE 5000"
    findings = auditor.run_audit()
    assert any("PORT_DRIFT" in f[1] for f in findings)
    assert any("EXPOSE 5000 != Graph Port 3000" in f[1] for f in findings)
    
    # Failure case: Compose mismatch
    auditor.artifacts["Dockerfile"] = "FROM node\nEXPOSE 3000"
    auditor.artifacts["docker-compose.yml"] = "api:\n  ports:\n    - \"8080:5000\""
    findings = auditor.run_audit()
    assert any("PORT_DRIFT" in f[1] for f in findings)
    assert any("Compose port 5000 != Graph Port 3000" in f[1] for f in findings)
