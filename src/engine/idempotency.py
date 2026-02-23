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
            # Multi-document support
            docs = list(yaml.safe_load_all(content))
            if not docs: return content
            
            stable_docs = []
            for doc in docs:
                if doc is None: continue
                # Re-dump with sorted keys and standard indent
                stable_docs.append(yaml.safe_dump(doc, default_flow_style=False, sort_keys=True, indent=2, allow_unicode=True))
            
            return "---\n".join(stable_docs)
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
        lines = content.splitlines()
        cleaned = []
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # Normalize instruction case
            parts = line.split(maxsplit=1)
            if len(parts) > 0:
                keyword = parts[0].upper()
                if keyword in ["FROM", "RUN", "CMD", "LABEL", "EXPOSE", "ENV", "ADD", "COPY", "ENTRYPOINT", "VOLUME", "USER", "WORKDIR", "ARG", "ONBUILD", "STOPSIGNAL", "HEALTHCHECK", "SHELL"]:
                    if len(parts) > 1:
                        cleaned.append(f"{keyword} {parts[1]}")
                    else:
                        cleaned.append(keyword)
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
