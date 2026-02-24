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
        block = Extractor.extract_code_block(content, "ya?ml")
        if not block:
            anchor_match = re.search(
                r"^(version:|apiVersion:|services:|kind:)",
                content, re.MULTILINE | re.IGNORECASE,
            )
            if anchor_match:
                block = content[anchor_match.start():].strip()
            else:
                block = content.strip()

        try:
            docs = list(yaml.safe_load_all(block))
            if not docs or all(d is None for d in docs):
                return ""
            cleaned_docs = [d for d in docs if d is not None]
            if len(cleaned_docs) == 1:
                return yaml.safe_dump(
                    cleaned_docs[0], default_flow_style=False,
                    sort_keys=False, allow_unicode=True,
                )
            else:
                return "---\n".join([
                    yaml.safe_dump(d, default_flow_style=False,
                                   sort_keys=False, allow_unicode=True)
                    for d in cleaned_docs
                ])
        except Exception as e:
            logger.warning(f"YAML extraction/sanitization failed: {e}")
            return block

    @staticmethod
    def extract_multiple_files(content: str) -> list:
        """
        Parses content for multiple files using the FILENAME: <path> format.
        Handles both fenced and bare block variants.
        """
        results = []

        primary_pattern = re.compile(
            r"(?:###\s*)?FILENAME:\s*([^\s\n]+)[ \t]*\n"
            r"(?:```(?:\w+)?\n)?(.*?)(?:```\n?|(?=(?:###\s*)?FILENAME:)|$)",
            re.DOTALL | re.IGNORECASE,
        )

        for match in primary_pattern.finditer(content):
            path = match.group(1).strip().lstrip("/")

            if len(path) > 255 or "\n" in path or path.startswith("apiVersion"):
                logger.warning(f"Skipping malformed FILENAME token: {path[:80]}...")
                continue

            raw_block = match.group(2).strip()
            clean_content = Extractor.extract_code_block(raw_block)
            if not clean_content:
                clean_content = raw_block

            if path.endswith((".yaml", ".yml")) or "docker-compose" in path:
                clean_content = Extractor.extract_yaml(clean_content)

            if clean_content:
                results.append({"path": path, "content": clean_content})

        return results
