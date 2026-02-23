# -*- coding: utf-8 -*-
import logging
import re
from typing import List, Tuple
from src.engine.severity import Severity
from src.engine.graph import ArchitectureGraph

logger = logging.getLogger("devops-agent")

class IntegrityAuditor:
    """
    Performs global cross-artifact consistency checks.
    Ensures Docker, Compose, K8s, and Nginx are in sync.
    """
    
    def __init__(self, graph: ArchitectureGraph):
        self.graph = graph
        self.artifacts = {} # path -> content

    def add_artifact(self, path: str, content: str):
        self.artifacts[path] = content

    def run_audit(self) -> List[Tuple[Severity, str]]:
        """
        Checks for cross-artifact drift.
        """
        findings = []
        
        # 1. Port Consistency Check
        findings.extend(self._check_port_consistency())
        
        # 2. Image Tag Consistency
        findings.extend(self._check_image_pinnings())
        
        # 3. Service Naming
        findings.extend(self._check_service_names())

        return findings

    def _check_port_consistency(self) -> List[Tuple[Severity, str]]:
        errors = []
        for svc_name, svc in self.graph.nodes.items():
            expected_port = svc.port
            
            # Check Dockerfile
            dockerfile = self.artifacts.get("Dockerfile") or self.artifacts.get(f"{svc_name}/Dockerfile")
            if dockerfile:
                expose_match = re.search(r'EXPOSE\s+(\d+)', dockerfile)
                if expose_match and int(expose_match.group(1)) != expected_port:
                    errors.append((Severity.HIGH, f"PORT_DRIFT: {svc_name} Dockerfile EXPOSE {expose_match.group(1)} != Graph Port {expected_port}"))

            # Check Compose
            compose = self.artifacts.get("docker-compose.yml") or self.artifacts.get("docker-compose.yaml")
            if compose:
                # Naive regex for compose ports
                port_match = re.search(rf'{svc_name}:.*ports:.*\n.*-.*"(\d+):(\d+)"', compose, re.DOTALL)
                if port_match and int(port_match.group(2)) != expected_port:
                    errors.append((Severity.HIGH, f"PORT_DRIFT: {svc_name} Compose port {port_match.group(2)} != Graph Port {expected_port}"))

        return errors

    def _check_image_pinnings(self) -> List[Tuple[Severity, str]]:
        errors = []
        # Check if Dockerfile and Compose image tags match
        for svc_name, svc in self.graph.nodes.items():
            # Extract FROM from Dockerfile
            dockerfile = self.artifacts.get("Dockerfile") or self.artifacts.get(f"{svc_name}/Dockerfile")
            if dockerfile:
                from_match = re.search(r'FROM\s+([^\s\n]+)', dockerfile, re.I)
                if from_match:
                    df_tag = from_match.group(1).split(':')[-1] if ':' in from_match.group(1) else "latest"
                    
                    # Check Compose image
                    compose = self.artifacts.get("docker-compose.yml") or self.artifacts.get("docker-compose.yaml")
                    if compose:
                        img_match = re.search(rf'{svc_name}:.*image:\s*([^\s\n]+)', compose, re.DOTALL)
                        if img_match:
                            cp_tag = img_match.group(1).split(':')[-1] if ':' in img_match.group(1) else "latest"
                            if df_tag != cp_tag and cp_tag != "latest": # Allow latest in compose if Dockerfile is specific
                                errors.append((Severity.HIGH, f"VERSION_DRIFT: {svc_name} tag mismatch. Dockerfile({df_tag}) != Compose({cp_tag})"))
        return errors

    def _check_service_names(self) -> List[Tuple[Severity, str]]:
        errors = []
        # Ensure k8s names match graph names
        for svc_name in self.graph.nodes:
            manifest = self.artifacts.get("k8s/manifest.yaml") or self.artifacts.get("deployment.yaml")
            if manifest and svc_name not in manifest:
                errors.append((Severity.MEDIUM, f"NAME_DRIFT: Service '{svc_name}' missing from K8s manifest."))
        return errors
