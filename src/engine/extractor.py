# -*- coding: utf-8 -*-
import re
import yaml
import logging

logger = logging.getLogger("devops-agent")

class Extractor:
    """
    Robustly extracts code or YAML blocks from LLM responses, 
    stripping prose and ensuring semantic cleanliness.
    """
    
    @staticmethod
    def extract_code_block(content: str, language: str = None) -> str:
        """
        Extracts the first code block matching the language if provided, 
        else the first code block.
        """
        if language:
            pattern = rf"```(?:{language})?\n(.*?)```"
        else:
            pattern = r"```(?:\w+)?\n(.*?)```"
            
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def extract_yaml(content: str) -> str:
        """
        Specialized YAML extraction that finds the root anchor, 
        strips prose, and re-serializes for idempotency.
        """
        # 1. Try fenced block first
        block = Extractor.extract_code_block(content, "ya?ml")
        if not block:
            # 2. Try to find start of YAML content if no backticks
            anchor_match = re.search(r'^(version:|apiVersion:|services:|kind:)', content, re.MULTILINE | re.IGNORECASE)
            if anchor_match:
                block = content[anchor_match.start():].strip()
            else:
                block = content.strip()

        # 3. Clean up and re-serialize to strip trailing prose and ensure valid YAML
        try:
            # We use safe_load_all to handle multi-document K8s manifests
            docs = list(yaml.safe_load_all(block))
            if not docs or all(d is None for d in docs):
                return ""
            
            # Clean docs
            cleaned_docs = [d for d in docs if d is not None]
            
            if len(cleaned_docs) == 1:
                return yaml.safe_dump(cleaned_docs[0], default_flow_style=False, sort_keys=True, allow_unicode=True)
            else:
                return "---\n".join([yaml.safe_dump(d, default_flow_style=False, sort_keys=True, allow_unicode=True) for d in cleaned_docs])
                
        except Exception as e:
            logger.warning(f"YAML extraction/sanitization failed: {e}")
            # If parsing fails, we return the block as-is but it might be "broken"
            return block

    @staticmethod
    def extract_multiple_files(content: str) -> list[dict[str, str]]:
        """
        Parses content for multiple files using the FILENAME: <path> format.
        """
        results = []
        # Support both '### FILENAME:' and 'FILENAME:'
        pattern = r"(?:###\s*)?FILENAME:\s*([^\s\n]+).?\n(.*?)(?=\n(?:###\s*)?FILENAME:|$)"
        matches = re.finditer(pattern, content, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            path = match.group(1).strip().strip('/')
            raw_block = match.group(2).strip()
            
            # Try to extract from ``` if present in the block
            clean_content = Extractor.extract_code_block(raw_block)
            if not clean_content:
                clean_content = raw_block
                
            # If it's YAML, sanitize it
            if path.endswith(('.yaml', '.yml')) or "docker-compose" in path:
                clean_content = Extractor.extract_yaml(clean_content)
                
            results.append({"path": path, "content": clean_content})
            
        return results
