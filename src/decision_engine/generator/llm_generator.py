import os
import logging
import re
import time
from typing import Any, Dict

from src.decision_engine.contracts.infra_spec import InfraSpec
from src.utils.prompt_loader import render_prompt, ALLOWED_TEMPLATE_VARS
from src.utils.errors import LLMError

log = logging.getLogger(__name__)

# Per-task-type prompt char limits — keeps prompts within LLM context windows
_TASK_LIMITS: dict[str, int] = {
    "dockerfile":      8000,
    "docker_compose":  8000,
    "kubernetes":      4000,
    "k8s":             4000,
    "gitops_manifests":4000,
    "cicd":            8000,
    "ci":              8000,
    "github_actions":  8000,
    "default":         5000,
}
_MAX_PROMPT_CHARS = int(os.environ.get("MAX_PROMPT_CHARS", "8000"))


class LLMGenerator:
    def __init__(self, client: Any, model_name: str):
        self.client = client
        self.model_name = model_name

    def generate(
        self,
        prompt_template: str,
        context: Dict[str, Any],
        task_type: str = "default",
    ) -> InfraSpec:
        # Filter context to allowed vars only — prevents PromptInjectionError
        safe_context: Dict[str, Any] = {
            k: v for k, v in context.items() if k in ALLOWED_TEMPLATE_VARS
        }

        full_prompt = render_prompt(prompt_template, safe_context)

        # Hard cap — must come after all appends
        max_chars = min(_TASK_LIMITS.get(task_type, _TASK_LIMITS["default"]), _MAX_PROMPT_CHARS)
        if len(full_prompt) > max_chars:
            log.warning(
                "Truncating prompt %d → %d chars (task=%s)",
                len(full_prompt), max_chars, task_type,
            )
            full_prompt = full_prompt[:max_chars] + "\n...[TRUNCATED]..."

        system_prompt = (
            "You are a Senior DevOps Engineer generating "
            "production-ready infrastructure code."
        )

        t0 = time.perf_counter()
        try:
            raw = self.client.call(full_prompt, system_prompt=system_prompt)
            log.info(
                "llm_call_ok",
                extra={"task": task_type, "latency_ms": round((time.perf_counter() - t0) * 1000, 1)},
            )
        except Exception as e:
            log.error("llm_call_failed", extra={"task": task_type, "error": str(e)})
            return InfraSpec(
                file_content="",
                model_name=self.model_name,
                violations=[f"Generation failed: {str(e)}"],
            )

        return InfraSpec(file_content=self._clean_markdown(raw), model_name=self.model_name)

    def _clean_markdown(self, info: str) -> str:
        if isinstance(info, list):
            info = "\n".join([str(i) for i in info])
        info = str(info).strip()

        # If the response contains FILENAME markers, return from first one
        idx = info.find("FILENAME:")
        if idx != -1:
            return info[idx:]

        # Extract largest ``` block
        blocks = re.findall(r"```(?:[\w+-]+)?\n(.*?)\n*```", info, re.DOTALL)
        if blocks:
            return max(blocks, key=len).strip()

        # Fallback: find first known directive line
        for line in info.splitlines():
            stripped = line.strip()
            if stripped.startswith(("FROM ", "apiVersion:", "name:", "on:", "jobs:")):
                return info[info.find(stripped):]

        return info
