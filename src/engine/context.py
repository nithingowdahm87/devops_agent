import os

class ContextExtractor:
    def analyze_repo(self, repo_path: str) -> dict:
        context = {
            "language": "unknown",
            "runtime_version": "unknown",
            "has_terraform": False,
            "multi_service": False,
            "environment": "production"
        }

        # Detect Node
        if os.path.exists(os.path.join(repo_path, "package.json")):
            context["language"] = "node"
            context["runtime_version"] = self._detect_runtime_version(repo_path)
        # Detect Python
        elif os.path.exists(os.path.join(repo_path, "requirements.txt")) or os.path.exists(os.path.join(repo_path, "pyproject.toml")):
            context["language"] = "python"
        
        # Detect Go
        elif os.path.exists(os.path.join(repo_path, "go.mod")):
            context["language"] = "go"

        # Detect Terraform
        context["has_terraform"] = any(
            f.endswith(".tf") for f in os.listdir(repo_path) if os.path.isfile(os.path.join(repo_path, f))
        )

        return context

    def _detect_runtime_version(self, repo_path: str) -> str:
        # Simplistic detection
        nvmrc_path = os.path.join(repo_path, ".nvmrc")
        if os.path.exists(nvmrc_path):
            with open(nvmrc_path, 'r') as f:
                return f.read().strip()
        return "20" # Default fallback
    
def extract_context(repo_path: str) -> dict:
    return ContextExtractor().analyze_repo(repo_path)
