import re
from typing import Any, Dict
from src.decision_engine.contracts.infra_spec import InfraSpec
from src.utils.prompt_loader import render_prompt


class LLMGenerator:
    def __init__(self, client: Any, model_name: str):
        self.client = client
        self.model_name = model_name

    def generate(self, prompt_template: str, context: Dict[str, Any]) -> InfraSpec:
        full_prompt = render_prompt(prompt_template, context)

        try:
            raw_response = self.client.call(full_prompt)
        except Exception as e:
            return InfraSpec(
                file_content="",
                model_name=self.model_name,
                violations=[f"Generation failed: {str(e)}"],
            )

        cleaned_content = self._clean_markdown(raw_response)

        return InfraSpec(
            file_content=cleaned_content,
            model_name=self.model_name,
        )

    def _clean_markdown(self, info: str) -> str:
        """
        Preserve multi-file FILENAME: blocks completely intact.
        For single-file responses, strip just the outer markdown fence.
        """
        if isinstance(info, list):
            info = "\n".join([str(i) for i in info])

        info = info.strip()

        # Multi-file: contains FILENAME: markers — return as-is so the
        # orchestrator's multifile parser can find all blocks.
        if "FILENAME:" in info:
            return info

        # Single-file: extract content from the first code fence
        if "```" in info:
            match = re.search(r"```[\w.-]*\r?\n(.*?)```", info, re.DOTALL)
            if match:
                return match.group(1).strip()
            # Fallback: strip all fence markers
            cleaned = re.sub(r"```[\w.-]*", "", info)
            return cleaned.replace("```", "").strip()

        return info
