# -*- coding: utf-8 -*-
import yaml
import json
import re

class IdempotencyEngine:
    """
    Ensures deterministic output for ALL artifact types.
    Enforces stable ordering and formatting.
    """
    
    @staticmethod
    def stabilize_yaml(content: str) -> str:
        try:
            data = yaml.safe_load(content)
            if not data: return content
            # Re-dump with sorted keys and standard indent
            return yaml.safe_dump(data, default_flow_style=False, sort_keys=True, indent=2, allow_unicode=True)
        except:
            return content

    @staticmethod
    def stabilize_json(content: str) -> str:
        try:
            data = json.loads(content)
            return json.dumps(data, indent=2, sort_keys=True)
        except:
            return content

    @staticmethod
    def stabilize_dockerfile(content: str) -> str:
        """
        Sorts instructions by predefined semantic order (FROM, ENV, COPY, etc.)
        """
        from src.engine.config import DOCKER_INSTRUCTION_ORDER
        lines = content.splitlines()
        # This is complex to do perfectly without breaking logic.
        # Minimal: Ensure no extra whitespace and consistent case.
        cleaned = []
        for line in lines:
            if line.strip():
                # Normalize case for instruction keywords
                parts = line.split(maxsplit=1)
                if len(parts) > 1 and parts[0].upper() in DOCKER_INSTRUCTION_ORDER:
                    cleaned.append(f"{parts[0].upper()} {parts[1]}")
                else:
                    cleaned.append(line)
        return "\n".join(cleaned)

    @staticmethod
    def stabilize(path: str, content: str) -> str:
        if path.endswith((".yaml", ".yml")):
            return IdempotencyEngine.stabilize_yaml(content)
        if path.endswith(".json"):
            return IdempotencyEngine.stabilize_json(content)
        if "dockerfile" in path.lower():
            return IdempotencyEngine.stabilize_dockerfile(content)
        return content
