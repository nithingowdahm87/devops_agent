"""
LLMGenerator — top-level generation class.
Wires together: cache → multi-provider sampler → constitution critique.
Drop-in replacement for the LLMGenerator class in the old llm.py.
"""
from __future__ import annotations
import re, logging
from src.engine import cache as prompt_cache
from src.engine.sampler import Sampler
from src.engine.constitution import Constitution
from src.engine.models import GeneratedFile
from src.engine.llm import call_llm

log = logging.getLogger(__name__)


class LLMGenerator:
    def __init__(self):
        self.sampler     = Sampler()
        self.constitution = Constitution(llm_client=None)
        self.system_prompt = self._load("configs/prompts/system/system_core.md")

    def _load(self, path: str) -> str:
        try:
            with open(path) as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def _task_prompt(self, task_type: str) -> str:
        return self._load({
            "docker": "configs/prompts/docker/docker_production.md",
            "k8s":    "configs/prompts/k8s/k8s_production.md",
            "ci":     "configs/prompts/cicd/cicd_production.md",
        }.get(task_type.lower(), ""))

    def generate(self, task_type: str, context: dict) -> list[GeneratedFile]:
        task_prompt  = self._task_prompt(task_type)
        if not task_prompt:
            raise ValueError(f"Unknown task type: {task_type}")

        context_str  = "\n".join(f"{k}: {v}" for k, v in context.items())
        user_prompt  = f"{task_prompt}\n\nAPPLICATION CONTEXT:\n{context_str}"

        # ── Step 1: Check cache first ────────────────────────────────────────
        cached = prompt_cache.get(self.system_prompt, user_prompt, task_type)
        if cached:
            log.info("Returning cached result for task_type=%s", task_type)
            return self._parse_files(cached)

        # ── Step 2: Multi-provider consensus sampling ────────────────────────
        log.info("Sampling from 3 providers in parallel (task=%s)…", task_type)
        candidates = self.sampler.sample(user_prompt, task_type=task_type)

        if not candidates:
            log.error("All providers failed — no candidates generated.")
            return []

        # Best-scored candidate is first (sampler sorts by rule coverage)
        winner = candidates[0]
        log.info("Winner selected (score-based). %d candidate(s) evaluated.", len(candidates))

        # ── Step 3: Constitutional critique on winner ────────────────────────
        files = self._parse_files(winner)
        critiqued = []
        for f in files:
            # Constitution now uses task-aware routing via call_llm
            cf = self.constitution.critique(f, task_type)
            critiqued.append(cf)

        # ── Step 4: Cache the final output ──────────────────────────────────
        final_text = "\n\n".join(f"FILENAME: {f.path}\n```\n{f.content}\n```" for f in critiqued)
        prompt_cache.set(self.system_prompt, user_prompt, task_type, final_text)

        return critiqued

    def _parse_files(self, response: str) -> list[GeneratedFile]:
        files = []
        pattern = r"(?:###\s*)?FILENAME:\s*([^\s\n]+).*\n(?:```[\w]*\n)?(.*?)(?:```|$)"
        for m in re.finditer(pattern, response, re.DOTALL | re.IGNORECASE):
            path    = m.group(1).strip().replace("\\", "/").strip("/")
            content = m.group(2).strip().rstrip("`").strip()
            if path and content:
                files.append(GeneratedFile(path=path, content=content))

        if not files:
            for lang, block in re.findall(r"```(.*?)\n(.*?)```", response, re.DOTALL):
                name = lang.split(":")[-1].strip() if "." in lang else "generated_file"
                files.append(GeneratedFile(path=name, content=block.strip()))

        return files


# ── Module-level shortcut (backward compatible) ───────────────────────────────
def generate(task_type: str, context: dict) -> list[GeneratedFile]:
    return LLMGenerator().generate(task_type, context)
