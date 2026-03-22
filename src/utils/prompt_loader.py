import os
import string
from pathlib import Path

def load_prompt(stage: str, role: str) -> str:
    """
    Load prompt template from configs/prompts/
    
    Args:
        stage: dockerfile, kubernetes, cicd, etc.
        role: writer_a_generalist, writer_b_security, etc.
    
    Returns:
        Prompt template string
    
    Raises:
        FileNotFoundError: If prompt file does not exist.
    """
    base_path = Path("configs/prompts")
    prompt_path = base_path / stage / f"{role}.md"
    
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")
    
    return prompt_path.read_text(encoding="utf-8")

class _SafeDict(dict):
    """Returns the original {key} placeholder for any missing key."""
    def __missing__(self, key):
        return "{" + key + "}"

def render_prompt(template: str, context: dict) -> str:
    """
    Render prompt template with application context.

    Supports both `{key}` and `{{ key }}` style placeholders used in
    the new GitHub Actions / ArgoCD prompts.
    """
    result = template

    # Keys we actually use in prompts
    keys_to_replace = [
        "context",
        "plan_summary",
        "project_name",
        "service_name",
        "svc_name",
        "service_path",
        "language",
        "resources",
        "rag_best_practices",
    ]

    for key in keys_to_replace:
        value = str(context.get(key, ""))
        # Support multiple placeholder styles
        patterns = [
            "{" + key + "}",              # {key}
            "{{ " + key + " }}",          # {{ key }}
            "{{" + key + "}}",            # {{key}}
        ]
        for pattern in patterns:
            if pattern in result:
                result = result.replace(pattern, value)

    return result
