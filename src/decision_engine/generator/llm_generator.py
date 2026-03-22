import os
import logging
from typing import Any, Dict

from src.decision_engine.contracts.infra_spec import InfraSpec
from src.utils.prompt_loader import render_prompt
from src.engine.llm import call_llm

log = logging.getLogger(__name__)

# Hard cap: ~2000 tokens leaving room for output + system prompt
_MAX_PROMPT_CHARS = int(os.environ.get("LOCAL_MAX_PROMPT_CHARS", "8000"))


def _artifact_type(task_type: str) -> str:
    t = task_type.lower()
    if t in ("dockerfile", "docker", "docker_compose"):
        return "docker"
    if t in ("kubernetes", "k8s", "gitops_manifests"):
        return "k8s"
    if t in ("cicd", "ci", "github_actions"):
        return "ci"
    return "docker"


def _fetch_rag_snippet(task_type: str, context: Dict[str, Any]) -> str:
    """
    Query local ChromaDB (src/engine/rag.py) for best-practice chunks
    relevant to this task + service language. Returns a short string
    safe to embed in the prompt.
    """
    try:
        from src.engine.rag import get_rag_context, RAGStore
        store = RAGStore()
        if store.collection.count() == 0:
            return ""   # nothing seeded yet, skip silently

        artifact_type = _artifact_type(task_type)
        lang  = context.get("language") or context.get("runtime") or "generic"
        stack = context.get("frameworks") or context.get("deps") or ""
        query = f"Best practices for {artifact_type} with {lang} service and stack {stack}"

        snippet = get_rag_context(query=query, artifact_type=artifact_type)
        # Hard cap snippet so it never blows the budget on its own
        return snippet[:1200] if snippet else ""
    except Exception as e:
        log.warning("RAG fetch failed (non-fatal): %s", e)
        return ""


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
        """
        1. Fetch RAG best-practice snippet (local Chroma, no internet)
        2. Inject it into the context so render_prompt fills {rag_best_practices}
        3. Render full prompt
        4. Hard-cap the prompt to stay within llama.cpp ctx window
        5. Call LLM and return InfraSpec
        """
        # 1. RAG snippet (pure local)
        rag_snippet = _fetch_rag_snippet(task_type, context)

        # 2. Inject into context for template placeholder
        enriched = dict(context)
        enriched["rag_best_practices"] = rag_snippet if rag_snippet else ""

        # 3. Render prompt (replaces {context}, {rag_best_practices}, etc.)
        full_prompt = render_prompt(prompt_template, enriched)

        # 4. If template had no {rag_best_practices} placeholder, append manually
        if rag_snippet and "{rag_best_practices}" not in prompt_template:
            full_prompt += f"\n\nRAG BEST PRACTICES:\n{rag_snippet}"

        # 5. Hard cap — must come LAST after all appends
        log.info("Prompt length for %s: %d chars", task_type, len(full_prompt))
        if len(full_prompt) > _MAX_PROMPT_CHARS:
            log.warning(
                "Truncating prompt from %d → %d chars (llama.cpp ctx guard)",
                len(full_prompt),
                _MAX_PROMPT_CHARS,
            )
            full_prompt = (
                full_prompt[:_MAX_PROMPT_CHARS]
                + "\n...[TRUNCATED — FIT LOCAL CONTEXT]..."
            )

        system_prompt = (
            "You are a Senior DevOps Engineer generating "
            "production-ready infrastructure code."
        )

        # 6. Call LLM
        try:
            raw_response = call_llm(system_prompt, full_prompt, task_type=task_type)
        except Exception as e:
            log.error("LLM call failed for task=%s: %s", task_type, e)
            return InfraSpec(
                file_content="",
                model_name=self.model_name,
                violations=[f"Generation failed: {str(e)}"],
            )

        # 7. Clean output
        cleaned = self._clean_markdown(raw_response)

        return InfraSpec(file_content=cleaned, model_name=self.model_name)

    def _clean_markdown(self, info: str) -> str:
        if isinstance(info, list):
            info = "\n".join([str(i) for i in info])
        if "FILENAME:" in info:
            return info.strip()
        if "```" in info:
            import re
            match = re.search(r"```(?:\w+)?\n(.*?)```", info, re.DOTALL)
            if match:
                return match.group(1).strip()
            return (
                info.replace("```yaml", "")
                    .replace("```dockerfile", "")
                    .replace("```json", "")
                    .replace("```", "")
                    .strip()
            )
        return info.strip()
