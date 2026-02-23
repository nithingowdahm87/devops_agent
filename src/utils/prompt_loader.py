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
    Uses simple replacement to avoid issues with code blocks containing {}
    """
    result = template
    # We only care about these primary keys in the orchestrator V2
    keys_to_replace = ["context", "plan_summary", "project_name"]
    
    for key in keys_to_replace:
        placeholder = "{" + key + "}"
        if placeholder in result:
            val = str(context.get(key, ""))
            result = result.replace(placeholder, val)
            
    return result
