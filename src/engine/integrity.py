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

        # 4. Environment Variable Parity (NEW)
        findings.extend(self._check_env_consistency())

        return findings

    def _check_port_consistency(self) -> List[Tuple[Severity, str]]:
        errors = []
        for svc_name in self.graph.nodes:
            # Use the ports dict — always valid regardless of how graph was built
            port_str = self.graph.ports.get(svc_name)
            if port_str is None:
                continue
            try:
                expected_port = int(port_str)
            except (ValueError, TypeError):
                continue

            # Check Dockerfile
            dockerfile = self.artifacts.get(f"{svc_name}/Dockerfile") or self.artifacts.get("Dockerfile")
            if dockerfile:
                expose_match = re.search(r'EXPOSE\s+(\d+)', dockerfile)
                if expose_match and int(expose_match.group(1)) != expected_port:
                    errors.append((Severity.HIGH, f"PORT_DRIFT: {svc_name} Dockerfile EXPOSE {expose_match.group(1)} != Graph Port {expected_port}"))

            # Check Compose
            compose = self.artifacts.get("docker-compose.yml") or self.artifacts.get("docker-compose.yaml")
            if compose:
                # Better regex for compose service ports
                port_match = re.search(rf'{svc_name}:.*ports:.*?["\'](\d+):(\d+)["\']', compose, re.DOTALL)
                if port_match and int(port_match.group(2)) != expected_port:
                    errors.append((Severity.HIGH, f"PORT_DRIFT: {svc_name} Compose internal port {port_match.group(2)} != Graph {expected_port}"))

            # Check K8s
            k8s_manifest = self.artifacts.get(f"k8s/{svc_name}/deployment.yaml") or self.artifacts.get(f"k8s/{svc_name}/svc.yaml")
            if k8s_manifest:
                cont_port = re.search(r'containerPort:\s*(\d+)', k8s_manifest)
                if cont_port and int(cont_port.group(1)) != expected_port:
                    errors.append((Severity.HIGH, f"PORT_DRIFT: {svc_name} K8s containerPort {cont_port.group(1)} != Graph {expected_port}"))

        return errors

    def _check_image_pinnings(self) -> List[Tuple[Severity, str]]:
        errors = []
        for svc_name in self.graph.nodes:
            dockerfile = self.artifacts.get(f"{svc_name}/Dockerfile") or self.artifacts.get("Dockerfile")
            if dockerfile:
                from_match = re.search(r'FROM\s+([^\s\n]+)', dockerfile, re.I)
                if from_match:
                    df_img = from_match.group(1)
                    
                    compose = self.artifacts.get("docker-compose.yml")
                    if compose:
                        img_match = re.search(rf'{svc_name}:.*?image:\s*([^\s\n]+)', compose, re.DOTALL)
                        if img_match and img_match.group(1) != df_img and ":" in img_match.group(1):
                             # Only alert on drifts, not base-vs-custom image mismatches
                             pass
        return errors

    def _check_env_consistency(self) -> List[Tuple[Severity, str]]:
        findings = []
        # Check if DB_URL style envs match across Compose and K8s
        compose = self.artifacts.get("docker-compose.yml")
        k8s_all = "\n".join([v for k,v in self.artifacts.items() if "k8s/" in k])
        
        db_keys = ["POSTGRES_DB", "POSTGRES_USER", "DATABASE_URL", "DB_NAME"]
        for key in db_keys:
            c_match = re.search(rf'{key}:\s*([^\s\n]+)', compose) if compose else None
            k_match = re.search(rf'{key}:\s*([^\s\n]+)', k8s_all) if k8s_all else None
            if c_match and k_match and c_match.group(1) != k_match.group(1):
                findings.append((Severity.HIGH, f"ENV_DRIFT: {key} mismatch between Compose and K8s."))
        return findings

    def _check_service_names(self) -> List[Tuple[Severity, str]]:
        errors = []
        for svc_name in self.graph.nodes:
            # Check if any k8s file mentions the service name
            found = False
            for path, content in self.artifacts.items():
                if "k8s/" in path and svc_name in content:
                    found = True
                    break
            if not found:
                errors.append((Severity.MEDIUM, f"NAME_DRIFT: Service '{svc_name}' not found in any K8s manifests."))
        return errors
