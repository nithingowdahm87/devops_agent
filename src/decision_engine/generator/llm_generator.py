import os
import logging
from typing import Any, Dict

from src.decision_engine.contracts.infra_spec import InfraSpec
from src.utils.prompt_loader import render_prompt
from src.engine.llm import call_llm

log = logging.getLogger(__name__)

# Hard cap: ~2000 tokens leaving room for output + system prompt
# Kimchi (kimi-k2.6) handles 256k context; keep prompt under ~8k chars for speed
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
        if not store.collection or store.collection.count() == 0:
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
        info = str(info).strip()

        # 0. Aggressive preamble strip — reasoning models often emit meta-text before
        #    the actual file content. Scan line-by-line and find the first "real" line.
        REASONING_HINTS = (
            "the user is", "the user wants", "i need to", "i will", "i should",
            "looking at", "fixing", "broken file", "validation error",
            "i cannot", "i can't", "no actual file", "content was not",
            "paste your", "package.json", "i don't see", "i do not see",
            "here is", "there is no", "not provided", "not valid",
            "senior devops", "senior patch", "fix the provided",
            "catch-22", "this is a", "actually, looking",
        )
        DIRECTIVE_HINTS = (
            "from ", "# syntax=", "# stage", "arg ",
            "apiversion:", "kind:", "metadata:",
            "name:", "on:", "jobs:", "permissions:",
            "version:", "services:", "networks:",
            "---", "```", "filename:",
        )
        lines = info.splitlines()
        start_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip().lower()
            # If we hit a reasoning phrase, skip past it
            if any(h in stripped for h in REASONING_HINTS):
                start_idx = i + 1
                continue
            # If we hit a directive, everything from here is likely real content
            if any(stripped.startswith(h) for h in DIRECTIVE_HINTS):
                start_idx = i
                break
        if start_idx > 0:
            info = "\n".join(lines[start_idx:]).strip()

        # 1. If the response contains FILENAME markers, trust the orchestrator's
        #    multifile parser and return the raw text from the first FILENAME.
        idx = info.find("FILENAME:")
        if idx != -1:
            return info[idx:]

        # 2. Extract all ``` blocks and return the largest one (most likely the actual code)
        import re
        blocks = re.findall(r"```(?:[\w+-]+)?\n(.*?)\n*```", info, re.DOTALL)
        if blocks:
            # Return the longest code block; reasoning text is usually shorter
            best = max(blocks, key=len)
            return best.strip()

        # 3. Fallback: if no code blocks, try to find a line starting with a known directive
        for line in info.splitlines():
            stripped = line.strip()
            if stripped.startswith(("FROM ", "apiVersion:", "name:", "on:", "jobs:")):
                return info[info.find(stripped):]

        return info
