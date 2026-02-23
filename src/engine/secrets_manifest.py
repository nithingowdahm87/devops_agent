# -*- coding: utf-8 -*-
import logging
from src.tools.file_ops import write_file

logger = logging.getLogger("devops-agent")

class SecretsManifest:
    """
    Generates a documentation file listing all required secrets for the project.
    Learns secrets from CI scripts and architecture analysis.
    """
    
    @staticmethod
    def generate(project_path: str, artifacts: dict):
        """
        Scans artifacts for secret references and writes SECRETS_REFERENCE.md.
        """
        secrets = set()
        
        # Scan artifacts
        for path, content in artifacts.items():
            import re
            # GHA
            if ".github/workflows" in path:
                matches = re.findall(r'\${{\s*secrets\.([A-Z_][A-Z0-9_]*)\s*}}', content)
                secrets.update(matches)
            # Compose
            if "docker-compose" in path:
                matches = re.findall(r'\${([A-Z_][A-Z0-9_]*)}', content)
                secrets.update([m for m in matches if "PASSWORD" in m or "SECRET" in m or "TOKEN" in m or "KEY" in m])
            # K8s
            if "k8s/" in path:
                # Look for name: in Secret objects
                if "kind: Secret" in content:
                    names = re.findall(r'name:\s*([a-z0-9](?:[-a-z0-9]*[a-z0-9])?)', content)
                    for n in names: 
                        if "secret" in n or "cred" in n: secrets.add(n.upper().replace("-", "_"))

        if not secrets:
            logger.info("No secrets detected for manifest.")
            return
            
        logger.info(f"🔑 Found {len(secrets)} secrets. Generating manifest...")
        
        manifest = "# SECRETS_REFERENCE.md\n\n"
        manifest += "The following secrets must be configured in your CI/CD provider (e.g., GitHub Secrets).\n\n"
        manifest += "| Secret Name | Description | Required For |\n"
        manifest += "|-------------|-------------|--------------|\n"
        
        for secret in sorted(list(secrets)):
            stage = "CI/CD"
            if "DOCKER" in secret: stage = "Docker Push"
            if "KUBE" in secret: stage = "K8s Deployment"
            manifest += f"| `{secret}` | Required by pipeline | {stage} |\n"
            
        import os
        write_file(os.path.join(project_path, "SECRETS_REFERENCE.md"), manifest)
        print("📄 Generated SECRETS_REFERENCE.md")
