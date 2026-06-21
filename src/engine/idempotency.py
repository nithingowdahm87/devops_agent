# -*- coding: utf-8 -*-
import yaml
import json
import re

class AegisSafeLoader(yaml.SafeLoader):
    """Custom loader that preserves 'on'/'off'/'yes'/'no' as strings (YAML 1.2 semantics)."""
    pass

# Copy SafeLoader resolver table and strip boolean resolvers for these prefixes
AegisSafeLoader.yaml_implicit_resolvers = {
    k: [r for r in v if r[0] != "tag:yaml.org,2002:bool"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.copy().items()
}

# Keep true/false bools — they are parsed via t/T/f/F which we leave alone.
# Add back the specific true/false resolver explicitly.
bool_true_false = re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$", re.X)
for ch in ("t", "T", "f", "F"):
    AegisSafeLoader.yaml_implicit_resolvers.setdefault(ch, []).insert(
        0, ("tag:yaml.org,2002:bool", bool_true_false)
    )

class IdempotencyEngine:
    """
    Ensures deterministic output for ALL artifact types.
    Enforces stable ordering and formatting.
    """
    
    @staticmethod
    def stabilize_yaml(content: str) -> str:
        try:
            # Multi-document support
            docs = list(yaml.load_all(content, Loader=AegisSafeLoader))
            if not docs: return content
            
            stable_docs = []
            for doc in docs:
                if doc is None: continue
                # Re-dump with standard indent — PRESERVE key order for readability
                dumped = yaml.safe_dump(doc, default_flow_style=False, sort_keys=False, indent=2, allow_unicode=True)
                # Restore idiomatic unquoted 'on'/'off' keys (e.g. GitHub Actions)
                # PyYAML quotes them to avoid YAML 1.1 bool ambiguity; for output artifacts plain scalars are preferred.
                dumped = re.sub(r"^'on':", "on:", dumped, flags=re.MULTILINE)
                dumped = re.sub(r"^'off':", "off:", dumped, flags=re.MULTILINE)
                dumped = re.sub(r"^'yes':", "yes:", dumped, flags=re.MULTILINE)
                dumped = re.sub(r"^'no':", "no:", dumped, flags=re.MULTILINE)
                stable_docs.append(dumped)
            
            return "---\n".join(stable_docs)
        except Exception:
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
