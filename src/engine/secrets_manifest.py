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
        
        # Scan CI artifacts
        for path, content in artifacts.items():
            if ".github/workflows" in path:
                import re
                matches = re.findall(r'\${{\s*secrets\.([A-Z_][A-Z0-9_]*)\s*}}', content)
                secrets.update(matches)
                
        if not secrets:
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
